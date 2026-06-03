package nestedonly

func PublicA() {
	go func() {
		doWork()
		doMore()
	}()
	defer func() {
		cleanup()
	}()
	select {
	case <-done:
	default:
	}
}

func PublicB() {
	go func() {
		doWork()
		doMore()
	}()
	defer func() {
		cleanup()
	}()
	select {
	case <-done:
	default:
	}
}

func PublicC() {
	go func() {
		doWork()
		doMore()
	}()
	defer func() {
		cleanup()
	}()
	select {
	case <-done:
	default:
	}
}

func priv1() int { return 1 }
func priv2() int { return 2 }

// The remainder is padding so the file clears the 200-LoC outline threshold
// without introducing any further declarations, doc blockquote, or imports —
// keeping the truncation ladder's later steps as no-ops so that lowering the
// budget exercises step 1 (drop nested) in isolation while private markers
// remain on the two private one-line helpers above.
// padding line
// padding line
// padding line
// padding line
// padding line
// padding line
// padding line
// padding line
// padding line
// padding line
// padding line
// padding line
// padding line
// padding line
// padding line
// padding line
// padding line
// padding line
// padding line
// padding line
// padding line
// padding line
// padding line
// padding line
// padding line
// padding line
// padding line
// padding line
// padding line
// padding line
// padding line
// padding line
// padding line
// padding line
// padding line
// padding line
// padding line
// padding line
// padding line
// padding line
// padding line
// padding line
// padding line
// padding line
// padding line
// padding line
// padding line
// padding line
// padding line
// padding line
// padding line
// padding line
// padding line
// padding line
// padding line
// padding line
// padding line
// padding line
// padding line
// padding line
// padding line
// padding line
// padding line
// padding line
// padding line
// padding line
// padding line
// padding line
// padding line
// padding line
// padding line
// padding line
// padding line
// padding line
// padding line
// padding line
// padding line
// padding line
// padding line
// padding line
// padding line
// padding line
// padding line
// padding line
// padding line
// padding line
// padding line
// padding line
// padding line
// padding line
// padding line
// padding line
// padding line
// padding line
// padding line
// padding line
// padding line
// padding line
// padding line
// padding line
// padding line
// padding line
// padding line
// padding line
// padding line
// padding line
// padding line
// padding line
// padding line
// padding line
// padding line
// padding line
// padding line
// padding line
// padding line
// padding line
// padding line
// padding line
// padding line
// padding line
// padding line
// padding line
// padding line
// padding line
// padding line
// padding line
// padding line
// padding line
// padding line
// padding line
// padding line
// padding line
// padding line
// padding line
// padding line
// padding line
// padding line
// padding line
// padding line
// padding line
// padding line
// padding line
// padding line
// padding line
// padding line
// padding line
// padding line
// padding line
// padding line
// padding line
// padding line
// padding line
// padding line
// padding line
// padding line
// padding line
// padding line
// padding line
// padding line
// padding line
// padding line
// padding line
