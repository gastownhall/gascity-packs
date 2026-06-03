package twofile

// Greet calls Foo from another file in the same package.
func Greet() string {
	return Foo("world")
}
