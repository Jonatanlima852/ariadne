package contractversion

import "testing"

func TestValidateAcceptsSupportedMajorAndRejectsInvalidVersions(t *testing.T) {
	for _, version := range []string{"2.0.0", "2.4.2"} {
		if err := Validate(version); err != nil {
			t.Fatalf("Validate(%q) = %v", version, err)
		}
	}
	for _, version := range []string{"", "0.1.0", "1.0.0", "3.0.0", "2.0", "v2.0.0"} {
		if err := Validate(version); err == nil {
			t.Fatalf("Validate(%q) accepted", version)
		}
	}
}
