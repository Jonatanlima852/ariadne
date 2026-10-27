package contractversion

import (
	"fmt"
	"strconv"
	"strings"
)

const Current = "2.0.0"
const SupportedMajor = 2

func Validate(version string) error {
	parts := strings.Split(version, ".")
	if len(parts) != 3 {
		return fmt.Errorf("contract_version must use semantic versioning: %q", version)
	}
	major, err := strconv.Atoi(parts[0])
	if err != nil {
		return fmt.Errorf("contract_version must use semantic versioning: %q", version)
	}
	for _, part := range parts[1:] {
		if _, err := strconv.Atoi(part); err != nil {
			return fmt.Errorf("contract_version must use semantic versioning: %q", version)
		}
	}
	if major != SupportedMajor {
		return fmt.Errorf("unsupported contract major version %d; supported major is %d", major, SupportedMajor)
	}
	return nil
}
