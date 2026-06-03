package sample

import (
	"fmt"
	"strings"
)

// Greet builds a greeting. It uses fmt and strings but NOT os, so `os` is an
// unused import that goimports must remove; `fmt`/`strings` are also written
// out of canonical order (strings before fmt) so the importer must sort them.
func Greet(name string) string {
	return fmt.Sprintf("hello, %s", strings.ToUpper(name))
}
