// Package startup exposes the address chosen by the OS to a local supervisor.
package startup

import (
	"log/slog"
	"os"
)

func ConfigureLogging() {
	if os.Getenv("ARIADNE_JSON_LOGS") == "1" {
		slog.SetDefault(slog.New(slog.NewJSONHandler(os.Stderr, nil)))
	}
}

// Ready is optional for existing deployments. Rename prevents partial reads.
// The supervisor must still check gRPC readiness after reading this address.
func Ready(address string) error {
	path := os.Getenv("ARIADNE_READY_FILE")
	if path == "" {
		return nil
	}
	if err := os.WriteFile(path+".tmp", []byte(address+"\n"), 0600); err != nil {
		return err
	}
	return os.Rename(path+".tmp", path)
}
