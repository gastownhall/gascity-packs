package demo

// Fixture for the go-interface-any intent. The empty-interface type appears in
// a parameter, a return type and a map value type; all become `any`.
func Wrap(x interface{}) interface{} {
	return x
}

func Bag() map[string]interface{} {
	return map[string]interface{}{}
}
