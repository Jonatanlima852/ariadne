package mission

import (
	"context"
	"fmt"
	"sort"
	"time"

	"github.com/google/uuid"
	"google.golang.org/protobuf/proto"
	"google.golang.org/protobuf/types/known/structpb"
	"google.golang.org/protobuf/types/known/timestamppb"

	pb "ariadne/runtime/gen/go/contract/v1"
	"ariadne/runtime/services/internal/events"
	"ariadne/runtime/services/orchestrator/internal/workflow"
)

const (
	// DefaultPlannerCapability é a capacidade procurada no Registry quando
	// MissionRequest.planner_capability vem vazio.
	DefaultPlannerCapability = "mission-planning"
	// PlannerTaskType identifica a tarefa enviada ao planejador em cada rodada.
	PlannerTaskType = "MISSION_PLANNING"
	// RootTaskType identifica a tarefa raiz sintética que agrupa a missão.
	RootTaskType = "MISSION"
	// maxConsecutiveInvalidPlans é o número de respostas inválidas seguidas
	// do planejador que aborta a missão (regra 3 da especificação).
	maxConsecutiveInvalidPlans = 3
)

type TaskExecutor interface {
	Execute(context.Context, *pb.Task) (*pb.TaskResult, *pb.ErrorInfo)
}
type Discoverer interface {
	Discover(context.Context, []string) ([]*pb.AgentDescriptor, error)
}
type EventLogger interface{ Log(events.Event) }

// Dependencies reúne tudo que o laço reutiliza do orquestrador: o executor de
// tarefas (retry e reassignment), a descoberta no Registry, o validador e o
// store de workflows (compartilhados com o engine criado por missão), o store
// de missões e o logger de eventos.
type Dependencies struct {
	Executor   TaskExecutor
	Discoverer Discoverer
	Validator  *workflow.Validator
	Workflows  workflow.Store
	Missions   Store
	Logger     EventLogger
}

type Runner struct{ deps Dependencies }

func New(deps Dependencies) *Runner {
	if deps.Validator == nil {
		deps.Validator = workflow.NewValidator(workflow.DefaultValidationLimits())
	}
	if deps.Workflows == nil {
		deps.Workflows = workflow.NewInMemoryStore()
	}
	return &Runner{deps: deps}
}

func DefaultLimits() *pb.MissionLimits {
	return &pb.MissionLimits{MaxRounds: 10, MaxParallel: 4, RoundDeadlineMs: 30_000, PlannerDeadlineMs: 120_000, MissionDeadlineMs: 0}
}

// effectiveLimits devolve uma cópia dos limites com os padrões aplicados a
// todo campo ausente ou não positivo. mission_deadline_ms = 0 significa sem limite.
func effectiveLimits(limits *pb.MissionLimits) *pb.MissionLimits {
	effective := DefaultLimits()
	if limits == nil {
		return effective
	}
	if limits.MaxRounds > 0 {
		effective.MaxRounds = limits.MaxRounds
	}
	if limits.MaxParallel > 0 {
		effective.MaxParallel = limits.MaxParallel
	}
	if limits.RoundDeadlineMs > 0 {
		effective.RoundDeadlineMs = limits.RoundDeadlineMs
	}
	if limits.PlannerDeadlineMs > 0 {
		effective.PlannerDeadlineMs = limits.PlannerDeadlineMs
	}
	if limits.MissionDeadlineMs > 0 {
		effective.MissionDeadlineMs = limits.MissionDeadlineMs
	}
	return effective
}

// Run executa a missão de forma síncrona até um estado terminal. O segundo
// retorno só é usado para falhas antes de a missão existir (requisição inválida).
func (r *Runner) Run(ctx context.Context, request *pb.MissionRequest) (*pb.MissionResult, *pb.ErrorInfo) {
	return r.run(ctx, request, nil)
}

func (r *Runner) run(parent context.Context, request *pb.MissionRequest, created func()) (*pb.MissionResult, *pb.ErrorInfo) {
	if failure := validateRequest(request); failure != nil {
		return nil, failure
	}
	request = proto.Clone(request).(*pb.MissionRequest)
	ensureIdentity(request)
	if r.deps.Missions != nil {
		if existing, _ := r.deps.Missions.Get(request.MissionId); existing != nil {
			return nil, missionError(pb.ErrorCode_ERROR_CODE_INVALID_TASK, "mission already exists: "+request.MissionId)
		}
	}

	limits := effectiveLimits(request.Limits)
	now := timestamppb.Now()
	root := &pb.Task{
		TaskId: "mission-" + request.MissionId, Type: RootTaskType, Goal: request.Goal,
		Payload: cloneStruct(request.Context), Status: pb.TaskStatus_TASK_STATUS_CREATED,
		Trace: proto.Clone(request.Trace).(*pb.TraceContext), CreatedAt: now, Metadata: request.Metadata,
	}
	ctx, cancel := parent, context.CancelFunc(func() {})
	if limits.MissionDeadlineMs > 0 {
		ctx, cancel = context.WithTimeout(parent, time.Duration(limits.MissionDeadlineMs)*time.Millisecond)
	}
	defer cancel()

	m := &run{
		runner: r, parent: parent, ctx: ctx, request: request, limits: limits, root: root,
		context: cloneStruct(request.Context),
		result: &pb.MissionResult{
			MissionId: request.MissionId, Status: pb.MissionStatus_MISSION_STATUS_CREATED,
			Context: cloneStruct(request.Context), Trace: proto.Clone(request.Trace).(*pb.TraceContext),
			CreatedAt: now, RootTaskId: root.TaskId,
		},
		// Um engine por missão: paralelismo e prazo por rodada vêm dos limites
		// da missão, mas executor, validador, store e logger são compartilhados.
		engine: workflow.NewEngineWithOptions(r.deps.Executor, r.deps.Validator, r.deps.Workflows, r.deps.Logger, workflow.EngineOptions{
			MaxParallelism: int(limits.MaxParallel),
			TotalTimeout:   time.Duration(limits.RoundDeadlineMs) * time.Millisecond,
		}),
	}
	m.save()
	if created != nil {
		created()
	}
	m.log("MISSION_CREATED", 0, "", "goal="+request.Goal)
	m.loop()
	return m.result, nil
}

// run é o estado de uma missão em execução.
type run struct {
	runner  *Runner
	parent  context.Context
	ctx     context.Context
	request *pb.MissionRequest
	limits  *pb.MissionLimits
	root    *pb.Task
	result  *pb.MissionResult
	context *structpb.Struct
	history []*pb.RoundSummary
	engine  *workflow.Engine
	invalid int
}

func (m *run) loop() {
	for round := int32(1); round <= m.limits.MaxRounds; round++ {
		if m.ctx.Err() != nil {
			m.finishInterrupted(round - 1)
			return
		}
		if finished := m.executeRound(round); finished {
			return
		}
	}
	m.finish(pb.MissionStatus_MISSION_STATUS_FAILED, missionError(pb.ErrorCode_ERROR_CODE_EXECUTION_FAILED,
		fmt.Sprintf("mission exhausted max_rounds=%d without DONE", m.limits.MaxRounds)), m.limits.MaxRounds)
}

// executeRound realiza uma rodada completa: planejar, validar, executar,
// mesclar contexto e registrar. Devolve true quando a missão terminou.
func (m *run) executeRound(round int32) bool {
	record := &pb.MissionRound{Round: round, StartedAt: timestamppb.Now()}
	m.log("MISSION_ROUND_STARTED", round, "", "")
	m.setStatus(pb.MissionStatus_MISSION_STATUS_PLANNING)

	// Regra 1: capacidades vivas do Registry, sem filtro.
	agents, err := m.runner.deps.Discoverer.Discover(m.ctx, nil)
	if err != nil {
		if m.ctx.Err() != nil {
			m.closeRound(record)
			m.finishInterrupted(round)
			return true
		}
		record.PlannerSummary = "registry discovery failed: " + err.Error()
		m.closeRound(record)
		m.finish(pb.MissionStatus_MISSION_STATUS_FAILED, missionError(pb.ErrorCode_ERROR_CODE_AGENT_UNAVAILABLE, record.PlannerSummary), round)
		return true
	}
	plannerRequest := &pb.PlannerRequest{
		MissionId: m.request.MissionId, Goal: m.request.Goal, Round: round,
		Context: cloneStruct(m.context), History: m.history,
		AvailableCapabilities: summarizeCapabilities(agents), Limits: m.limits,
	}
	task, err := m.plannerTask(plannerRequest)
	if err != nil {
		record.PlannerSummary = err.Error()
		m.closeRound(record)
		m.finish(pb.MissionStatus_MISSION_STATUS_FAILED, missionError(pb.ErrorCode_ERROR_CODE_EXECUTION_FAILED, err.Error()), round)
		return true
	}

	// Regra 2: o planejador é uma tarefa comum, com retry e reassignment.
	plannerResult, failure := m.runner.deps.Executor.Execute(m.ctx, task)
	// Clonada depois da execução para preservar assigned_agent_id e attempt,
	// que o executor preenche na própria tarefa.
	record.PlannerTask = proto.Clone(task).(*pb.Task)
	record.PlannerResult = plannerResult
	if plannerResult != nil {
		record.PlannerAgentId = plannerResult.AgentId
	}
	if m.ctx.Err() != nil {
		record.PlannerSummary = "planner interrupted"
		m.closeRound(record)
		m.finishInterrupted(round)
		return true
	}
	if failure == nil && (plannerResult == nil || plannerResult.Status != pb.TaskStatus_TASK_STATUS_COMPLETED) {
		failure = missionError(pb.ErrorCode_ERROR_CODE_EXECUTION_FAILED, "planner did not complete")
		if plannerResult != nil && plannerResult.Error != nil {
			failure = plannerResult.Error
		}
	}
	if failure != nil {
		record.PlannerSummary = "planner failed: " + failure.Message
		m.log("MISSION_PLANNED", round, record.PlannerAgentId, "action=NONE error="+failure.Message)
		m.closeRound(record)
		m.finish(pb.MissionStatus_MISSION_STATUS_FAILED, failure, round)
		return true
	}

	// Regra 3: decodificar e validar a resposta.
	response, plan, err := decodePlannerResponse(plannerResult.Output)
	if err == nil {
		err = m.checkResponse(response, plan)
	}
	if err != nil {
		return m.invalidResponse(round, record, response, plan, err)
	}
	m.invalid = 0
	record.Action = response.Action
	record.PlannerSummary = response.Summary
	m.log("MISSION_PLANNED", round, record.PlannerAgentId, "action="+actionName(response.Action)+" summary="+response.Summary)

	// Regra 4 (primeira parte): context_update mescla antes de executar.
	m.mergeContext(response.ContextUpdate)

	switch response.Action {
	case pb.PlannerAction_PLANNER_ACTION_DONE:
		m.closeRound(record)
		m.result.Output = cloneStruct(response.Output)
		m.finish(pb.MissionStatus_MISSION_STATUS_COMPLETED, nil, round)
		return true
	case pb.PlannerAction_PLANNER_ACTION_ABORT:
		reason := response.Reason
		if reason == "" {
			reason = "planner aborted the mission without a reason"
		}
		m.closeRound(record)
		m.finish(pb.MissionStatus_MISSION_STATUS_ABORTED, missionError(pb.ErrorCode_ERROR_CODE_EXECUTION_FAILED, reason), round)
		return true
	}

	// Regra 4 (segunda parte): executar o DAG com o engine da missão.
	definition := m.applyDefaults(plan)
	record.Plan = definition
	m.setStatus(pb.MissionStatus_MISSION_STATUS_RUNNING)
	workflowResult, failure := m.engine.Execute(m.ctx, proto.Clone(m.root).(*pb.Task), definition)
	summary := &pb.RoundSummary{Round: round, Action: pb.PlannerAction_PLANNER_ACTION_PLAN, PlannerSummary: response.Summary}
	if failure != nil {
		summary.Status = pb.WorkflowStatus_WORKFLOW_STATUS_FAILED
		summary.PlannerSummary = joinSummary(response.Summary, "execution error: "+failure.Message)
		record.PlannerSummary = summary.PlannerSummary
	} else {
		record.Result = workflowResult
		summary.StepResults = workflowResult.StepResults
		summary.Status = workflowResult.Status
		// Regra 5: só o workflow completo alimenta o contexto; falhas de passo
		// ficam no histórico e o planejador decide na próxima rodada.
		if workflowResult.Status == pb.WorkflowStatus_WORKFLOW_STATUS_COMPLETED {
			m.mergeContext(workflowResult.Output)
		}
	}
	m.history = append(m.history, summary)
	m.closeRound(record)
	if m.ctx.Err() != nil {
		m.finishInterrupted(round)
		return true
	}
	return false
}

// invalidResponse registra uma rodada falha, devolve o erro ao planejador
// pelo planner_summary do histórico e aborta após três seguidas.
func (m *run) invalidResponse(round int32, record *pb.MissionRound, response *pb.PlannerResponse, plan *pb.WorkflowDefinition, err error) bool {
	m.invalid++
	if response != nil {
		record.Action = response.Action
	}
	record.Plan = plan
	record.PlannerSummary = "invalid planner response: " + err.Error()
	m.log("MISSION_PLANNED", round, record.PlannerAgentId, "action="+actionName(record.Action)+" invalid="+err.Error())
	m.history = append(m.history, &pb.RoundSummary{
		Round: round, Action: record.Action, Status: pb.WorkflowStatus_WORKFLOW_STATUS_FAILED, PlannerSummary: record.PlannerSummary,
	})
	m.closeRound(record)
	if m.invalid >= maxConsecutiveInvalidPlans {
		m.finish(pb.MissionStatus_MISSION_STATUS_ABORTED, missionError(pb.ErrorCode_ERROR_CODE_INVALID_TASK,
			fmt.Sprintf("%d consecutive invalid planner responses; last error: %s", m.invalid, err.Error())), round)
		return true
	}
	return false
}

func (m *run) checkResponse(response *pb.PlannerResponse, plan *pb.WorkflowDefinition) error {
	switch response.Action {
	case pb.PlannerAction_PLANNER_ACTION_PLAN:
		if plan == nil {
			return fmt.Errorf("PLAN requires a plan")
		}
		if err := m.runner.deps.Validator.Validate(plan); err != nil {
			return fmt.Errorf("plan rejected: %w", err)
		}
	case pb.PlannerAction_PLANNER_ACTION_DONE:
		if response.Output == nil {
			return fmt.Errorf("DONE requires output")
		}
	case pb.PlannerAction_PLANNER_ACTION_ABORT:
	default:
		return fmt.Errorf("action is required: PLAN, DONE or ABORT")
	}
	return nil
}

// plannerTask monta a tarefa comum enviada ao planejador (regra 2).
func (m *run) plannerTask(request *pb.PlannerRequest) (*pb.Task, error) {
	payload, err := encodePlannerRequest(request)
	if err != nil {
		return nil, err
	}
	capability := m.request.PlannerCapability
	if capability == "" {
		capability = DefaultPlannerCapability
	}
	task := &pb.Task{
		TaskId: uuid.NewString(), Type: PlannerTaskType, Goal: m.request.Goal, Payload: payload,
		RequiredCapabilities: []string{capability}, Status: pb.TaskStatus_TASK_STATUS_CREATED,
		Trace: &pb.TraceContext{
			TraceId: m.root.Trace.TraceId, SpanId: uuid.NewString(),
			ParentSpanId: m.root.Trace.SpanId, CorrelationId: m.request.MissionId,
		},
		CreatedAt: timestamppb.Now(), DeadlineMs: m.limits.PlannerDeadlineMs, ParentTaskId: m.root.TaskId,
		SelectionPolicy: m.request.DefaultSelectionPolicy, Metadata: m.request.Metadata,
	}
	if m.request.DefaultRetryPolicy != nil {
		task.RetryPolicy = proto.Clone(m.request.DefaultRetryPolicy).(*pb.RetryPolicy)
	}
	return task, nil
}

// applyDefaults devolve uma cópia do plano em que passos sem política
// herdam default_retry_policy e default_selection_policy (regra 4).
func (m *run) applyDefaults(plan *pb.WorkflowDefinition) *pb.WorkflowDefinition {
	definition := proto.Clone(plan).(*pb.WorkflowDefinition)
	for _, step := range definition.Steps {
		if step == nil || step.TaskTemplate == nil {
			continue
		}
		if step.TaskTemplate.RetryPolicy == nil && m.request.DefaultRetryPolicy != nil {
			step.TaskTemplate.RetryPolicy = proto.Clone(m.request.DefaultRetryPolicy).(*pb.RetryPolicy)
		}
		if step.TaskTemplate.SelectionPolicy == pb.SelectionPolicy_SELECTION_POLICY_FIRST_AVAILABLE {
			step.TaskTemplate.SelectionPolicy = m.request.DefaultSelectionPolicy
		}
	}
	return definition
}

func (m *run) mergeContext(update *structpb.Struct) {
	m.context = mergeStruct(m.context, update)
}

func (m *run) setStatus(status pb.MissionStatus) {
	m.result.Status = status
	m.save()
}

// closeRound fecha o registro da rodada, anexa ao resultado e publica o evento.
func (m *run) closeRound(record *pb.MissionRound) {
	record.ContextAfter = cloneStruct(m.context)
	record.CompletedAt = timestamppb.Now()
	m.result.Rounds = append(m.result.Rounds, record)
	m.result.Context = cloneStruct(m.context)
	m.save()
	details := "action=" + actionName(record.Action)
	if record.Result != nil {
		details += " status=" + record.Result.Status.String() + " run_id=" + record.Result.RunId
	}
	m.log("MISSION_ROUND_COMPLETED", record.Round, record.PlannerAgentId, details)
}

func (m *run) finishInterrupted(round int32) {
	if m.parent.Err() == context.Canceled {
		m.finish(pb.MissionStatus_MISSION_STATUS_CANCELLED, missionError(pb.ErrorCode_ERROR_CODE_EXECUTION_FAILED, "mission cancelled"), round)
		return
	}
	m.finish(pb.MissionStatus_MISSION_STATUS_TIMEOUT, missionError(pb.ErrorCode_ERROR_CODE_TIMEOUT, "mission deadline exceeded"), round)
}

func (m *run) finish(status pb.MissionStatus, failure *pb.ErrorInfo, round int32) {
	m.result.Status = status
	m.result.Error = failure
	m.result.Context = cloneStruct(m.context)
	m.result.CompletedAt = timestamppb.Now()
	m.save()
	details := ""
	if failure != nil {
		details = failure.Message
	}
	m.log(terminalEvent(status), round, "", details)
}

func terminalEvent(status pb.MissionStatus) string {
	switch status {
	case pb.MissionStatus_MISSION_STATUS_COMPLETED:
		return "MISSION_COMPLETED"
	case pb.MissionStatus_MISSION_STATUS_ABORTED:
		return "MISSION_ABORTED"
	case pb.MissionStatus_MISSION_STATUS_CANCELLED:
		return "MISSION_CANCELLED"
	case pb.MissionStatus_MISSION_STATUS_TIMEOUT:
		return "MISSION_TIMEOUT"
	default:
		return "MISSION_FAILED"
	}
}

func (m *run) save() {
	if m.runner.deps.Missions == nil {
		return
	}
	_ = m.runner.deps.Missions.Save(m.result)
}

func (m *run) log(eventType string, round int32, agentID, details string) {
	if m.runner.deps.Logger == nil {
		return
	}
	m.runner.deps.Logger.Log(events.Event{
		EventID: uuid.NewString(), TaskID: m.root.TaskId, Type: eventType, AgentID: agentID,
		TraceID: m.root.Trace.TraceId, MissionID: m.request.MissionId, Round: round, Details: details,
	})
}

// summarizeCapabilities agrupa as capacidades dos agentes vivos por
// capability_id, contando quantos agentes oferecem cada uma.
func summarizeCapabilities(agents []*pb.AgentDescriptor) []*pb.CapabilitySummary {
	byID := map[string]*pb.CapabilitySummary{}
	for _, agent := range agents {
		if agent == nil {
			continue
		}
		seen := map[string]bool{}
		for _, capability := range agent.Capabilities {
			if capability == nil || capability.CapabilityId == "" || seen[capability.CapabilityId] {
				continue
			}
			seen[capability.CapabilityId] = true
			summary := byID[capability.CapabilityId]
			if summary == nil {
				summary = &pb.CapabilitySummary{CapabilityId: capability.CapabilityId}
				byID[capability.CapabilityId] = summary
			}
			if summary.Name == "" {
				summary.Name = capability.Name
			}
			if summary.Description == "" {
				summary.Description = capability.Description
			}
			summary.AgentCount++
		}
	}
	summaries := make([]*pb.CapabilitySummary, 0, len(byID))
	for _, summary := range byID {
		summaries = append(summaries, summary)
	}
	sort.Slice(summaries, func(i, j int) bool { return summaries[i].CapabilityId < summaries[j].CapabilityId })
	return summaries
}

// mergeStruct faz substituição rasa por chave: valores de update sobrescrevem
// os de base com a mesma chave; chaves ausentes em update são preservadas.
func mergeStruct(base, update *structpb.Struct) *structpb.Struct {
	merged := cloneStruct(base)
	if update == nil {
		return merged
	}
	for key, value := range update.Fields {
		merged.Fields[key] = proto.Clone(value).(*structpb.Value)
	}
	return merged
}

func cloneStruct(value *structpb.Struct) *structpb.Struct {
	if value == nil {
		return &structpb.Struct{Fields: map[string]*structpb.Value{}}
	}
	cloned := proto.Clone(value).(*structpb.Struct)
	if cloned.Fields == nil {
		cloned.Fields = map[string]*structpb.Value{}
	}
	return cloned
}

func joinSummary(parts ...string) string {
	joined := ""
	for _, part := range parts {
		if part == "" {
			continue
		}
		if joined != "" {
			joined += "; "
		}
		joined += part
	}
	return joined
}

func validateRequest(request *pb.MissionRequest) *pb.ErrorInfo {
	if request == nil {
		return missionError(pb.ErrorCode_ERROR_CODE_INVALID_TASK, "mission is required")
	}
	if request.Goal == "" {
		return missionError(pb.ErrorCode_ERROR_CODE_INVALID_TASK, "goal is required")
	}
	return nil
}

// ensureIdentity gera mission_id e trace quando o cliente não os informa.
func ensureIdentity(request *pb.MissionRequest) {
	if request.MissionId == "" {
		request.MissionId = uuid.NewString()
	}
	if request.Trace == nil {
		request.Trace = &pb.TraceContext{}
	}
	if request.Trace.TraceId == "" {
		request.Trace.TraceId = uuid.NewString()
	}
	if request.Trace.SpanId == "" {
		request.Trace.SpanId = uuid.NewString()
	}
	if request.Trace.CorrelationId == "" {
		request.Trace.CorrelationId = request.MissionId
	}
}

func missionError(code pb.ErrorCode, message string) *pb.ErrorInfo {
	return &pb.ErrorInfo{Code: code, Message: message}
}
