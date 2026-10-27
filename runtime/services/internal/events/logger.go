package events

import (
	"encoding/json"
	"log/slog"
	"os"
	"sync"
	"time"
)

type Event struct {
	EventID    string `json:"event_id"`
	TaskID     string `json:"task_id,omitempty"`
	Type       string `json:"type"`
	Timestamp  string `json:"timestamp"`
	AgentID    string `json:"agent_id,omitempty"`
	TraceID    string `json:"trace_id,omitempty"`
	WorkflowID string `json:"workflow_id,omitempty"`
	RunID      string `json:"run_id,omitempty"`
	StepID     string `json:"step_id,omitempty"`
	Attempt    int32  `json:"attempt,omitempty"`
	MissionID  string `json:"mission_id,omitempty"`
	Round      int32  `json:"round,omitempty"`
	Details    string `json:"details,omitempty"`
}

type Logger struct {
	mu   sync.Mutex
	file *os.File
}

func NewLogger(path string) (*Logger, error) {
	if err := os.MkdirAll(filepath(path), 0755); err != nil {
		return nil, err
	}
	file, err := os.OpenFile(path, os.O_APPEND|os.O_CREATE|os.O_WRONLY, 0644)
	if err != nil {
		return nil, err
	}
	return &Logger{file: file}, nil
}

func (l *Logger) Log(event Event) {
	event.Timestamp = time.Now().UTC().Format(time.RFC3339Nano)
	l.mu.Lock()
	defer l.mu.Unlock()
	line, err := json.Marshal(event)
	if err != nil {
		slog.Error("failed to marshal event", "err", err)
		return
	}
	if _, err := l.file.Write(append(line, '\n')); err != nil {
		slog.Error("failed to write event", "err", err)
	}
}

func (l *Logger) Close() { _ = l.file.Close() }

func filepath(path string) string {
	for index := len(path) - 1; index >= 0; index-- {
		if path[index] == '/' {
			return path[:index]
		}
	}
	return "."
}
