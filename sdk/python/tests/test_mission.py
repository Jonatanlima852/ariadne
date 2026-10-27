"""Cliente de missão, conversão do MissionResult e protocolo do planejador."""
import json
from pathlib import Path
import tempfile
import unittest

from google.protobuf import json_format, timestamp_pb2

from contract.v1 import contract_pb2 as pb
from ariadne_sdk import (
    Mission, MissionLimits, MissionResult, PlannerRequest, PlannerResponse,
    RuntimeClient, Scenario, Step, TaskResult, plan_step,
)
from ariadne_sdk.models import mapping_to_struct


def _timestamp(seconds):
    value = timestamp_pb2.Timestamp()
    value.FromSeconds(seconds)
    return value


def _task(task_id, goal, capability, payload, parent="root-1"):
    return pb.Task(
        task_id=task_id, type="MISSION_STEP", goal=goal, payload=mapping_to_struct(payload),
        required_capabilities=[capability], parent_task_id=parent,
    )


def _result(task_id, agent_id, output=None, *, failed=False):
    result = TaskResult(
        task_id=task_id, agent_id=agent_id,
        status="TASK_STATUS_FAILED" if failed else "TASK_STATUS_COMPLETED",
        output=output or {}, error_code="ERROR_CODE_EXECUTION_FAILED" if failed else None,
        error_message="agent exploded" if failed else None,
    ).to_proto()
    return result


def planner_result(task_id, agent_id, response):
    return TaskResult(
        task_id=task_id, agent_id=agent_id, status="TASK_STATUS_COMPLETED",
        output=response, metadata={"provider": "openai"},
    ).to_proto()


def build_mission_result(request):
    """Duas rodadas: PLAN com dois passos (um falha) e DONE com a saída final."""
    plan = pb.WorkflowDefinition(workflow_id="wf-1", final_step_id="merge", steps=[
        pb.WorkflowStep(step_id="pick", task_template=pb.Task(
            goal="pick items", required_capabilities=["picking"], payload=mapping_to_struct({"order": "o-1"}),
        )),
        pb.WorkflowStep(step_id="merge", depends_on=["pick"], task_template=pb.Task(
            goal="merge", required_capabilities=["merging"],
        ), input_bindings=[pb.ResultBinding(
            source_step_id="pick", source_path="output.items", target_field="items",
        )]),
    ])
    workflow = pb.WorkflowResult(
        workflow_id="wf-1", run_id="run-1", root_task_id="root-1",
        status=pb.WORKFLOW_STATUS_FAILED,
        step_results=[
            pb.WorkflowStepResult(
                step_id="pick", status=pb.WORKFLOW_STEP_STATUS_COMPLETED,
                task=_task("t-pick", "pick items", "picking", {"order": "o-1"}),
                result=_result("t-pick", "picker-1", {"items": ["a", "b"]}),
            ),
            pb.WorkflowStepResult(
                step_id="merge", status=pb.WORKFLOW_STEP_STATUS_FAILED,
                task=_task("t-merge", "merge", "merging", {"items": ["a", "b"]}),
                result=_result("t-merge", "merger-1", failed=True),
            ),
        ],
    )
    first_response = {
        "action": "PLAN",
        "plan": {"workflow_id": "wf-1", "final_step_id": "merge", "steps": [
            plan_step("pick", "picking", "pick items", payload={"order": "o-1"}),
            plan_step("merge", "merging", "merge", depends_on=["pick"], input_bindings=[{
                "source_step_id": "pick", "source_path": "output.items", "target_field": "items",
            }]),
        ]},
        "summary": "pick then merge",
        "context_update": {"attempt": 1},
    }
    second_response = {
        "action": "DONE",
        "output": {"items": ["a", "b"], "merged": False},
        "summary": "merge failed; returning partial result",
    }
    return pb.MissionResult(
        mission_id=request.mission_id, status=pb.MISSION_STATUS_COMPLETED,
        output=mapping_to_struct({"items": ["a", "b"], "merged": False}),
        context=mapping_to_struct({"warehouse": "W1", "attempt": 1}),
        root_task_id="root-1", trace=request.trace,
        created_at=_timestamp(100), completed_at=_timestamp(103),
        rounds=[
            pb.MissionRound(
                round=1, planner_agent_id="planner-llm", action=pb.PLANNER_ACTION_PLAN,
                plan=plan, result=workflow, planner_summary="pick then merge",
                context_after=mapping_to_struct({"warehouse": "W1", "attempt": 1}),
                started_at=_timestamp(100), completed_at=_timestamp(102),
                planner_result=planner_result("t-plan-1", "planner-llm", first_response),
            ),
            pb.MissionRound(
                round=2, planner_agent_id="planner-llm", action=pb.PLANNER_ACTION_DONE,
                planner_summary="merge failed; returning partial result",
                started_at=_timestamp(102), completed_at=_timestamp(103),
                planner_result=planner_result("t-plan-2", "planner-llm", second_response),
            ),
        ],
    )


class FakeMissionOrchestrator:
    def __init__(self, *, status=None, error=None):
        self.requests = []
        self.status = status
        self.error = error
        self.cancelled = False

    def RunMission(self, request, timeout=None):
        self.requests.append(("RunMission", request, timeout))
        if self.error:
            return pb.RunMissionResponse(error=pb.ErrorInfo(
                code=pb.ERROR_CODE_INVALID_TASK, message=self.error,
            ))
        result = build_mission_result(request.mission)
        if self.status is not None:
            result.status = self.status
            result.error.CopyFrom(pb.ErrorInfo(
                code=pb.ERROR_CODE_EXECUTION_FAILED, message="max rounds reached",
            ))
        return pb.RunMissionResponse(result=result)

    def StartMission(self, request):
        self.requests.append(("StartMission", request, None))
        return pb.StartMissionResponse(mission_id=request.mission.mission_id)

    def GetMission(self, request):
        status = pb.MISSION_STATUS_CANCELLED if self.cancelled else pb.MISSION_STATUS_RUNNING
        return pb.GetMissionResponse(result=pb.MissionResult(
            mission_id=request.mission_id, status=status,
        ))

    def CancelMission(self, request):
        self.cancelled = True
        return pb.CancelMissionResponse(result=pb.MissionResult(
            mission_id=request.mission_id, status=pb.MISSION_STATUS_CANCELLED,
        ))


class RunMissionTests(unittest.TestCase):
    def run_mission(self, stub=None, **options):
        stub = stub or FakeMissionOrchestrator()
        client = RuntimeClient("mission-test", orchestrator_stub=stub)
        result = client.run_mission(
            "Separe e consolide o pedido o-1", context={"warehouse": "W1"},
            limits={"max_rounds": 3, "max_parallel": 2}, retry_policy={"max_attempts": 2},
            selection_policy="least_loaded", metadata={"case": "demo"}, rpc_timeout=5, **options,
        )
        return client, stub, result

    def test_request_carries_goal_context_limits_policies_and_trace(self):
        client, stub, _ = self.run_mission()
        name, request, timeout = stub.requests[0]
        mission = request.mission
        self.assertEqual(name, "RunMission")
        self.assertEqual(timeout, 5)
        self.assertEqual(mission.goal, "Separe e consolide o pedido o-1")
        self.assertEqual(mission.planner_capability, "mission-planning")
        self.assertEqual(json_format.MessageToDict(mission.context), {"warehouse": "W1"})
        self.assertEqual(mission.limits.max_rounds, 3)
        self.assertEqual(mission.limits.max_parallel, 2)
        self.assertEqual(mission.default_retry_policy.max_attempts, 2)
        self.assertEqual(mission.default_selection_policy, pb.SELECTION_POLICY_LEAST_LOADED)
        self.assertEqual(json_format.MessageToDict(mission.metadata), {"case": "demo"})
        self.assertEqual(mission.trace.trace_id, client.trace_id)
        self.assertTrue(mission.mission_id)
        self.assertIn(mission.mission_id, client.missions)
        self.assertEqual([event["type"] for event in client.events], ["MISSION_SUBMITTED", "MISSION_FINISHED"])

    def test_result_exposes_rounds_steps_with_task_and_result(self):
        _, _, result = self.run_mission()
        self.assertIsInstance(result, MissionResult)
        self.assertEqual(result.status, "MISSION_STATUS_COMPLETED")
        self.assertEqual(result.output, {"items": ["a", "b"], "merged": False})
        self.assertEqual(result.context["warehouse"], "W1")
        self.assertEqual(result.duration_ms, 3000)
        self.assertEqual(len(result.rounds), 2)
        first, second = result.rounds
        self.assertEqual((first.round, first.action, first.planner_agent_id), (1, "PLANNER_ACTION_PLAN", "planner-llm"))
        self.assertEqual([step["step_id"] for step in first.plan_steps], ["pick", "merge"])
        self.assertEqual(first.plan_steps[1]["depends_on"], ["pick"])
        self.assertEqual(first.workflow_status, "WORKFLOW_STATUS_FAILED")
        self.assertEqual(first.duration_ms, 2000)
        pick, merge = first.steps
        self.assertEqual(pick.status, "WORKFLOW_STEP_STATUS_COMPLETED")
        self.assertEqual(pick.task["payload"], {"order": "o-1"})
        self.assertEqual(pick.task["required_capabilities"], ["picking"])
        self.assertEqual(pick.result["output"], {"items": ["a", "b"]})
        self.assertEqual(pick.agent_id, "picker-1")
        self.assertEqual(merge.status, "WORKFLOW_STEP_STATUS_FAILED")
        self.assertEqual(merge.task["payload"], {"items": ["a", "b"]})
        self.assertEqual(merge.error, "agent exploded")
        self.assertEqual(first.step["merge"].result["error"]["message"], "agent exploded")
        self.assertEqual(second.action, "PLANNER_ACTION_DONE")
        self.assertEqual(second.steps, [])
        self.assertEqual(second.planner_response["action"], "DONE")
        result.assert_completed().assert_agent_used("picker-1").assert_agent_used("planner-llm")
        with self.assertRaisesRegex(AssertionError, "not used"):
            result.assert_agent_used("nobody")

    def test_planner_calls_rebuild_request_and_decode_response(self):
        _, _, result = self.run_mission()
        calls = result.planner_calls
        self.assertEqual([call.round for call in calls], [1, 2])
        first, second = calls
        self.assertEqual(first.request["goal"], "Separe e consolide o pedido o-1")
        self.assertEqual(first.request["context"], {"warehouse": "W1"})
        self.assertEqual(first.request["limits"], {"max_rounds": 3, "max_parallel": 2})
        self.assertNotIn("history", first.request)
        self.assertEqual(first.response["action"], "PLAN")
        self.assertEqual(PlannerResponse.from_output(first.response).plan["final_step_id"], "merge")
        self.assertEqual(second.request["round"], 2)
        self.assertEqual(second.request["context"], {"warehouse": "W1", "attempt": 1})
        history = second.request["history"]
        self.assertEqual(len(history), 1)
        self.assertEqual(history[0]["action"], "PLANNER_ACTION_PLAN")
        self.assertEqual(history[0]["status"], "WORKFLOW_STATUS_FAILED")
        self.assertEqual([item["step_id"] for item in history[0]["step_results"]], ["pick", "merge"])
        self.assertEqual(history[0]["step_results"][1]["result"]["error"]["message"], "agent exploded")
        self.assertEqual(PlannerResponse.from_output(second.response).output["merged"], False)
        self.assertEqual(second.result.metadata["provider"], "openai")

    def test_to_dict_uses_proto_field_names_and_save_writes_json(self):
        _, _, result = self.run_mission()
        document = result.to_dict()
        self.assertEqual(document["mission_id"], result.mission_id)
        self.assertEqual(document["status"], "MISSION_STATUS_COMPLETED")
        self.assertEqual(document["root_task_id"], "root-1")
        self.assertEqual(document["created_at"], "1970-01-01T00:01:40Z")
        round_one = document["rounds"][0]
        self.assertEqual(round_one["planner_agent_id"], "planner-llm")
        self.assertEqual(round_one["plan"]["steps"][1]["input_bindings"][0]["source_step_id"], "pick")
        self.assertEqual(round_one["result"]["step_results"][0]["task"]["required_capabilities"], ["picking"])
        self.assertEqual(round_one["result"]["step_results"][1]["result"]["status"], "TASK_STATUS_FAILED")
        self.assertEqual(round_one["planner_result"]["output"]["action"], "PLAN")
        self.assertEqual(document["request"]["planner_capability"], "mission-planning")
        self.assertEqual(document["planner_calls"][1]["response"]["action"], "DONE")
        self.assertNotIn("missionId", json.dumps(document))
        with tempfile.TemporaryDirectory() as directory:
            path = result.save(Path(directory) / "nested" / "mission-result.json")
            self.assertEqual(json.loads(path.read_text(encoding="utf-8")), document)

    def test_status_mapping_and_assert_completed_failure(self):
        _, _, result = self.run_mission(FakeMissionOrchestrator(status=pb.MISSION_STATUS_FAILED))
        self.assertEqual(result.status, "MISSION_STATUS_FAILED")
        self.assertEqual(result.error, "max rounds reached")
        self.assertEqual(result.error_code, "ERROR_CODE_EXECUTION_FAILED")
        self.assertFalse(result.completed)
        with self.assertRaisesRegex(AssertionError, "max rounds reached"):
            result.assert_completed()

    def test_rejected_mission_raises_and_records_event(self):
        stub = FakeMissionOrchestrator(error="no planner available")
        client = RuntimeClient("rejected", orchestrator_stub=stub)
        with self.assertRaisesRegex(RuntimeError, "no planner available"):
            client.run_mission("goal")
        self.assertEqual(client.events[-1]["type"], "MISSION_REJECTED")

    def test_invalid_arguments_fail_before_any_rpc(self):
        stub = FakeMissionOrchestrator()
        client = RuntimeClient("invalid", orchestrator_stub=stub)
        for options, message in (
            (dict(goal=""), "non-empty"),
            (dict(goal="g", limits={"max_round": 1}), "unknown mission limit"),
            (dict(goal="g", limits={"max_rounds": -1}), "non-negative"),
            (dict(goal="g", selection_policy="typo"), "selection policy"),
            (dict(goal="g", retry_policy={"attempts": 2}), "retry policy"),
        ):
            with self.subTest(message=message), self.assertRaisesRegex(ValueError, message):
                client.run_mission(**options)
        self.assertEqual(stub.requests, [])

    def test_start_get_and_cancel_mission(self):
        stub = FakeMissionOrchestrator()
        client = RuntimeClient("async", orchestrator_stub=stub)
        mission_id = client.start_mission("goal", mission_id="m-async", limits=MissionLimits(max_rounds=2))
        self.assertEqual(mission_id, "m-async")
        self.assertEqual(stub.requests[0][1].mission.limits.max_rounds, 2)
        running = client.get_mission(mission_id)
        self.assertEqual(running.status, "MISSION_STATUS_RUNNING")
        self.assertEqual(running.goal, "goal")
        cancelled = client.cancel_mission(mission_id)
        self.assertEqual(cancelled.status, "MISSION_STATUS_CANCELLED")
        self.assertEqual(client.get_mission(mission_id).status, "MISSION_STATUS_CANCELLED")
        self.assertEqual(cancelled.to_dict()["request"]["mission_id"], "m-async")


class PlannerProtocolTests(unittest.TestCase):
    def test_request_decodes_contract_payload_and_rejects_unknown_fields(self):
        payload = {
            "mission_id": "m-1", "goal": "ship it", "round": 2,
            "context": {"warehouse": "W1"},
            "history": [{"round": 1, "action": "PLANNER_ACTION_PLAN", "status": "WORKFLOW_STATUS_COMPLETED",
                         "planner_summary": "first", "step_results": [{"step_id": "pick",
                         "status": "WORKFLOW_STEP_STATUS_COMPLETED", "result": {"task_id": "t", "agent_id": "a",
                         "status": "TASK_STATUS_COMPLETED", "output": {"items": 2}}}]}],
            "available_capabilities": [{"capability_id": "picking", "name": "Picking", "agent_count": 2}],
            # protojson (UseProtoNames) writes int64 fields as strings.
            "limits": {"max_rounds": 5, "round_deadline_ms": "30000", "planner_deadline_ms": "120000"},
        }
        request = PlannerRequest.from_payload(payload)
        self.assertEqual((request.mission_id, request.goal, request.round), ("m-1", "ship it", 2))
        self.assertEqual(request.context, {"warehouse": "W1"})
        self.assertEqual(request.capability_ids, ["picking"])
        self.assertEqual(request.last_round["step_results"][0]["result"]["output"], {"items": 2})
        self.assertEqual(request.limits, {"max_rounds": 5, "round_deadline_ms": "30000", "planner_deadline_ms": "120000"})
        self.assertEqual(request.to_dict()["available_capabilities"][0]["agent_count"], 2)
        with self.assertRaisesRegex(ValueError, "invalid planner request"):
            PlannerRequest.from_payload({**payload, "bogus": 1})
        with self.assertRaisesRegex(ValueError, "must be an object"):
            PlannerRequest.from_payload("goal")

    def test_plan_requires_non_empty_valid_plan(self):
        response = PlannerResponse.make_plan(
            [plan_step("pick", "picking", "pick", payload={"order": 1}),
             plan_step("merge", ["merging"], "merge", depends_on=["pick"], bdi_goal="merged")],
            summary="two steps", context_update={"stage": "picking"},
        )
        output = response.to_output()
        self.assertEqual(output["action"], "PLAN")
        self.assertEqual(output["plan"]["final_step_id"], "merge")
        self.assertEqual(output["plan"]["steps"][1]["bdi_goal"], "merged")
        self.assertEqual(output["context_update"], {"stage": "picking"})
        self.assertNotIn("output", output)
        self.assertNotIn("reason", output)
        # The orchestrator normalizes "PLAN" to the enum name before protojson decoding.
        envelope = {k: v for k, v in output.items() if k != "plan"}
        envelope["action"] = "PLANNER_ACTION_" + envelope["action"]
        self.assertEqual(json_format.ParseDict(envelope, pb.PlannerResponse()).action, pb.PLANNER_ACTION_PLAN)
        for plan, message in (
            (None, "requires a plan"),
            ({"steps": []}, "non-empty"),
            ({"steps": [plan_step("a", "x", "g")], "extra": 1}, "unknown fields"),
            ({"steps": [{**plan_step("a", "x", "g"), "deadline_ms": 5}]}, "unknown fields"),
            ({"steps": [plan_step("a", [], "g")]}, "required_capabilities"),
            ({"steps": [plan_step("a", "x", "g", depends_on=["b"])]}, "unknown step b"),
            ({"steps": [plan_step("a", "x", "g")], "final_step_id": "z"}, "unknown step z"),
            ({"steps": [plan_step("a", "x", "g"), plan_step("a", "x", "g")]}, "duplicate"),
            ({"steps": [plan_step("a", "x", "g", input_bindings=[{"source_step_id": "a"}])]}, "binding"),
        ):
            with self.subTest(message=message), self.assertRaisesRegex(ValueError, message):
                PlannerResponse("PLAN", plan=plan).to_output()

    def test_done_requires_output_and_abort_requires_reason(self):
        done = PlannerResponse.done({"total": 3}, summary="finished").to_output()
        self.assertEqual(done, {"action": "DONE", "output": {"total": 3}, "summary": "finished"})
        self.assertNotIn("plan", done)
        abort = PlannerResponse.abort("no capable agent").to_output()
        self.assertEqual(abort["action"], "ABORT")
        self.assertEqual(abort["reason"], "no capable agent")
        with self.assertRaisesRegex(ValueError, "DONE requires"):
            PlannerResponse("done").to_output()
        with self.assertRaisesRegex(ValueError, "ABORT requires"):
            PlannerResponse("PLANNER_ACTION_ABORT", reason="  ").to_output()
        with self.assertRaisesRegex(ValueError, "planner action"):
            PlannerResponse("RETRY").to_output()

    def test_from_output_round_trips_and_rejects_unknown_fields(self):
        output = PlannerResponse.done({"x": 1}).to_output()
        self.assertEqual(PlannerResponse.from_output(output).action, "DONE")
        self.assertEqual(PlannerResponse.from_output({**output, "action": "PLANNER_ACTION_DONE"}).action, "DONE")
        with self.assertRaisesRegex(ValueError, "unknown fields"):
            PlannerResponse.from_output({**output, "plan_id": 1})


if __name__ == "__main__":
    unittest.main()
