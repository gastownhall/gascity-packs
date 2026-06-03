package widget

import "fmt"

// Run exercises Helper from within the original package; after extraction this
// call must be qualified as helpers.Helper and the new package imported.
func Run() {
	fmt.Println(Helper("hello"))
	fmt.Println(stays())
}
