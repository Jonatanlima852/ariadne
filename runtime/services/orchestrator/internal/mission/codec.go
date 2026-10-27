package mission

import (
	"fmt"
	"strings"

	"google.golang.org/protobuf/encoding/protojson"
	"google.golang.org/protobuf/types/known/structpb"

	pb "ariadne/runtime/gen/go/contract/v1"
	"ariadne/runtime/services/orchestrator/internal/planning"
)

// encodePlannerRequest serializa o PlannerRequest como JSON com nomes de
// campo do .proto (snake_case) e o converte em Struct para viajar em
// Task.payload. É o formato que o contrato fixa para o planejador.
func encodePlannerRequest(request *pb.PlannerRequest) (*structpb.Struct, error) {
	encoded, err := protojson.MarshalOptions{UseProtoNames: true}.Marshal(request)
	if err != nil {
		return nil, fmt.Errorf("encode planner request: %w", err)
	}
	payload := &structpb.Struct{}
	if err := protojson.Unmarshal(encoded, payload); err != nil {
		return nil, fmt.Errorf("encode planner request payload: %w", err)
	}
	return payload, nil
}

// decodePlannerResponse lê TaskResult.output como PlannerResponse. O envelope
// (action, output, context_update, summary, reason) passa por protojson com
// campos desconhecidos proibidos; o campo `plan` usa o mesmo formato achatado
// que planning.DecodeDefinition já aceita, por isso é destacado antes.
// A resposta parcialmente decodificada é devolvida mesmo em erro, para que a
// rodada registre a ação declarada pelo planejador.
func decodePlannerResponse(output *structpb.Struct) (*pb.PlannerResponse, *pb.WorkflowDefinition, error) {
	if output == nil {
		return nil, nil, fmt.Errorf("planner returned no output")
	}
	fields := make(map[string]*structpb.Value, len(output.Fields))
	for key, value := range output.Fields {
		fields[key] = value
	}
	planValue, hasPlan := fields["plan"]
	delete(fields, "plan")
	normalizeAction(fields)

	encoded, err := protojson.Marshal(&structpb.Struct{Fields: fields})
	if err != nil {
		return nil, nil, fmt.Errorf("planner response is not valid JSON: %w", err)
	}
	response := &pb.PlannerResponse{}
	if err := (protojson.UnmarshalOptions{DiscardUnknown: false}).Unmarshal(encoded, response); err != nil {
		return nil, nil, fmt.Errorf("planner response rejected: %w", err)
	}

	if !hasPlan || planValue == nil {
		return response, nil, nil
	}
	if _, isNull := planValue.Kind.(*structpb.Value_NullValue); isNull {
		return response, nil, nil
	}
	planStruct := planValue.GetStructValue()
	if planStruct == nil {
		return response, nil, fmt.Errorf("plan must be a JSON object")
	}
	definition, err := planning.DecodeDefinition(planStruct)
	if err != nil {
		return response, nil, fmt.Errorf("plan rejected: %w", err)
	}
	response.Plan = definition
	return response, definition, nil
}

// normalizeAction aceita tanto "PLAN" quanto "PLANNER_ACTION_PLAN" (e
// minúsculas), convertendo para o nome completo do enum que o protojson exige.
func normalizeAction(fields map[string]*structpb.Value) {
	value := fields["action"]
	if value == nil {
		return
	}
	name, ok := value.Kind.(*structpb.Value_StringValue)
	if !ok {
		return
	}
	upper := strings.ToUpper(strings.TrimSpace(name.StringValue))
	if !strings.HasPrefix(upper, "PLANNER_ACTION_") {
		upper = "PLANNER_ACTION_" + upper
	}
	fields["action"] = structpb.NewStringValue(upper)
}

func actionName(action pb.PlannerAction) string {
	return strings.TrimPrefix(action.String(), "PLANNER_ACTION_")
}
