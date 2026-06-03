package widget

import "strings"

// Helper upper-cases the given string. It is exported and free of
// unexported package dependencies, so it is safe to lift into a new package.
func Helper(s string) string {
	return strings.ToUpper(s)
}

// stays is an unexported helper that must remain in this package and must
// NOT be dragged along when Helper is extracted.
func stays() string {
	return "stay"
}
