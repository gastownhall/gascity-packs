// Package trunc is engineered to exercise every step of the §5.3 truncation
// precedence ladder: it carries a multi-line package doc, many imports, public
// functions with nested significant constructs (goroutine / defer / select),
// and a large tail of private helpers, so that lowering the token budget cuts
// content in the normative order (nested, private decls, doc, imports).
// This second doc line exists only to be dropped at truncation step 4.
// This third doc line also exists only to be dropped at truncation step 4.
package trunc

import (
	"github.com/example/alpha"
	"github.com/example/bravo"
	"github.com/example/charlie"
	"github.com/example/delta"
	"github.com/example/echo"
	"github.com/example/foxtrot"
	"github.com/example/golf"
	"github.com/example/hotel"
	"github.com/example/india"
	"github.com/example/juliet"
	"github.com/example/kilo"
	"github.com/example/lima"
	"github.com/example/mike"
	"github.com/example/november"
	"github.com/example/oscar"
	"github.com/example/papa"
)

// PublicA drives a goroutine, a deferred cleanup, and a select.
func PublicA() {
	go func() {
		doWork()
		doMore()
	}()
	defer func() {
		cleanup()
		logIt()
	}()
	select {
	case <-done:
		return
	default:
	}
}

// PublicB drives a goroutine, a deferred cleanup, and a select.
func PublicB() {
	go func() {
		doWork()
		doMore()
	}()
	defer func() {
		cleanup()
		logIt()
	}()
	select {
	case <-done:
		return
	default:
	}
}

// PublicC drives a goroutine, a deferred cleanup, and a select.
func PublicC() {
	go func() {
		doWork()
		doMore()
	}()
	defer func() {
		cleanup()
		logIt()
	}()
	select {
	case <-done:
		return
	default:
	}
}

// PublicD drives a goroutine, a deferred cleanup, and a select.
func PublicD() {
	go func() {
		doWork()
		doMore()
	}()
	defer func() {
		cleanup()
		logIt()
	}()
	select {
	case <-done:
		return
	default:
	}
}

func helper00() int { return 0 }
func helper01() int { return 1 }
func helper02() int { return 2 }
func helper03() int { return 3 }
func helper04() int { return 4 }
func helper05() int { return 5 }
func helper06() int { return 6 }
func helper07() int { return 7 }
func helper08() int { return 8 }
func helper09() int { return 9 }
func helper10() int { return 10 }
func helper11() int { return 11 }
func helper12() int { return 12 }
func helper13() int { return 13 }
func helper14() int { return 14 }
func helper15() int { return 15 }
func helper16() int { return 16 }
func helper17() int { return 17 }
func helper18() int { return 18 }
func helper19() int { return 19 }
func helper20() int { return 20 }
func helper21() int { return 21 }
func helper22() int { return 22 }
func helper23() int { return 23 }
func helper24() int { return 24 }
func helper25() int { return 25 }
func helper26() int { return 26 }
func helper27() int { return 27 }
func helper28() int { return 28 }
func helper29() int { return 29 }
func helper30() int { return 30 }
func helper31() int { return 31 }
func helper32() int { return 32 }
func helper33() int { return 33 }
func helper34() int { return 34 }
func helper35() int { return 35 }
func helper36() int { return 36 }
func helper37() int { return 37 }
func helper38() int { return 38 }
func helper39() int { return 39 }
func extra000() int { return 0 }
func extra001() int { return 1 }
func extra002() int { return 2 }
func extra003() int { return 3 }
func extra004() int { return 4 }
func extra005() int { return 5 }
func extra006() int { return 6 }
func extra007() int { return 7 }
func extra008() int { return 8 }
func extra009() int { return 9 }
func extra010() int { return 10 }
func extra011() int { return 11 }
func extra012() int { return 12 }
func extra013() int { return 13 }
func extra014() int { return 14 }
func extra015() int { return 15 }
func extra016() int { return 16 }
func extra017() int { return 17 }
func extra018() int { return 18 }
func extra019() int { return 19 }
func extra020() int { return 20 }
func extra021() int { return 21 }
func extra022() int { return 22 }
func extra023() int { return 23 }
func extra024() int { return 24 }
func extra025() int { return 25 }
func extra026() int { return 26 }
func extra027() int { return 27 }
func extra028() int { return 28 }
func extra029() int { return 29 }
func extra030() int { return 30 }
func extra031() int { return 31 }
func extra032() int { return 32 }
func extra033() int { return 33 }
func extra034() int { return 34 }
func extra035() int { return 35 }
func extra036() int { return 36 }
func extra037() int { return 37 }
func extra038() int { return 38 }
func extra039() int { return 39 }
func extra040() int { return 40 }
func extra041() int { return 41 }
func extra042() int { return 42 }
func extra043() int { return 43 }
func extra044() int { return 44 }
func extra045() int { return 45 }
func extra046() int { return 46 }
func extra047() int { return 47 }
func extra048() int { return 48 }
func extra049() int { return 49 }
func extra050() int { return 50 }
func extra051() int { return 51 }
func extra052() int { return 52 }
func extra053() int { return 53 }
func extra054() int { return 54 }
func extra055() int { return 55 }
func extra056() int { return 56 }
func extra057() int { return 57 }
func extra058() int { return 58 }
func extra059() int { return 59 }
func extra060() int { return 60 }
func extra061() int { return 61 }
func extra062() int { return 62 }
func extra063() int { return 63 }
func extra064() int { return 64 }
func extra065() int { return 65 }
func extra066() int { return 66 }
func extra067() int { return 67 }
func extra068() int { return 68 }
func extra069() int { return 69 }
func extra070() int { return 70 }
func extra071() int { return 71 }
func extra072() int { return 72 }
func extra073() int { return 73 }
func extra074() int { return 74 }
func extra075() int { return 75 }
func extra076() int { return 76 }
func extra077() int { return 77 }
func extra078() int { return 78 }
func extra079() int { return 79 }
func extra080() int { return 80 }
func extra081() int { return 81 }
func extra082() int { return 82 }
func extra083() int { return 83 }
func extra084() int { return 84 }
func extra085() int { return 85 }
func extra086() int { return 86 }
func extra087() int { return 87 }
func extra088() int { return 88 }
func extra089() int { return 89 }
func extra090() int { return 90 }
func extra091() int { return 91 }
func extra092() int { return 92 }
