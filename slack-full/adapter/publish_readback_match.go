package main

import (
	"strings"
	"unicode"
	"unicode/utf8"
)

type slackReadbackLink struct {
	textStart, textEnd int
	target, label      string
	labeled            bool
}

func slackReadbackLinks(text string) ([]slackReadbackLink, [][2]int) {
	text = slackEntityUnescape.Replace(text)
	var result []slackReadbackLink
	var markup [][2]int
	rawEnd, textEnd := 0, 0
	for _, span := range slackCodeOrAngleSpan.FindAllStringIndex(text, -1) {
		textStart := textEnd + len(slackNormalizeUnescapedLinks(text[rawEnd:span[0]]))
		textEnd = textStart + len(slackNormalizeUnescapedLinks(text[span[0]:span[1]]))
		rawEnd = span[1]
		markup = append(markup, [2]int{textStart, textEnd})
		if text[span[0]] != '<' {
			continue
		}
		target, label, labeled := strings.Cut(text[span[0]+1:span[1]-1], "|")
		// A colon in angle-delimited prose is not enough to make a link.
		if strings.IndexFunc(target, unicode.IsSpace) < 0 && (slackReferenceTarget.MatchString(target) || slackAbsoluteLinkScheme.MatchString(target) ||
			strings.HasPrefix(target, "mailto:") || (labeled && slackLinkScheme.MatchString(target))) {
			result = append(result, slackReadbackLink{textStart, textEnd, target, label, labeled})
		}
	}
	return result, markup
}

// Align returned links with literal source text, then scan each complete source
// URL for its end. This separates URL bytes from prose even when Slack returns
// a link for only part of a URI. Explicit targets retain their identity, while
// all text after the token uses the existing Unicode/shortcode emoji units.
func slackReadbackTextMatches(expected, stored string) bool {
	expectedText, storedText := slackNormalizeLinks(expected), slackNormalizeLinks(stored)
	expectedLiterals, storedLiterals := slackLiteralPrefixCounts(expectedText), slackLiteralPrefixCounts(storedText)
	explicit, markup := slackReadbackLinks(expected)
	storedLinks, storedMarkup := slackReadbackLinks(stored)
	storedMarkupStarts := make(map[int]bool, len(storedMarkup))
	for _, span := range storedMarkup {
		storedMarkupStarts[span[0]] = true
	}
	// Removing angle markup must not join an explicit URI to its neighbors.
	// Scan each original span separately, retaining normalized byte offsets.
	var verbatim [][]int
	appendVerbatim := func(start, end int) {
		for _, span := range slackVerbatimSpan.FindAllStringIndex(expectedText[start:end], -1) {
			verbatim = append(verbatim, []int{start + span[0], start + span[1]})
		}
	}
	last := 0
	markupEnds := make(map[int]bool, len(markup))
	for _, span := range markup {
		appendVerbatim(last, span[0])
		appendVerbatim(span[0], span[1])
		last = span[1]
		markupEnds[last] = true
	}
	appendVerbatim(last, len(expectedText))
	explicitCursor, verbatimCursor := 0, 0
	suffixMarkupCursor := 0
	expectedCursor, storedCursor := 0, 0
	type suffixCheck struct {
		linkStart, expectedStart, storedStart int
		expectedEnd, storedEnd, limit         int
		tokenStart, tokenLimit                int
		independent                           bool
		markup, optional                      bool
	}
	var pendingSuffix *suffixCheck
	var suffixes []*suffixCheck
	var matchedSpans [][2]int
	finishSuffix := func(expectedEnd, storedEnd int) {
		if pendingSuffix != nil {
			pendingSuffix.expectedEnd = min(expectedEnd, pendingSuffix.limit)
			pendingSuffix.storedEnd = storedEnd
			suffixes = append(suffixes, pendingSuffix)
		}
	}
	// A mismatch with many repeated labels must not repeatedly fold growing
	// prefixes. Successful alignment consumes each span once; ambiguous failed
	// candidates share this byte budget, like the emoji fallback's state budget.
	budget := 8*(len(expectedText)+len(storedText)) + 100000
	compare := func(a, b string) bool {
		budget -= len(a) + len(b) + 1
		return budget >= 0 && slackNormalizedPrefixesMatch(a, b)
	}
	for _, link := range storedLinks {
		implicit := link.label != "" && (link.target == "http://"+link.label || link.target == "https://"+link.label ||
			(strings.HasPrefix(link.label, "www.") && len(link.label) > len("www.") && link.target == "http://"+strings.TrimPrefix(link.label, "www.")))
		fullURI := slackAbsoluteLinkScheme.MatchString(link.target) && (!link.labeled || link.label == link.target)
		prefix := storedText[storedCursor:link.textStart]
		rendered := storedText[link.textStart:link.textEnd]
		if rendered == "" {
			return false
		}
		exactPrefix := strings.HasPrefix(expectedText[expectedCursor:], prefix)
		if explicitCursor < len(explicit) {
			original := explicit[explicitCursor]
			// Use the known source offset before searching repeated labels.
			// When the prefix is exact, it already identifies the offset.
			// Literal counts reject a far-away same-target link in constant
			// time, so intervening auto-links do not repeatedly fold its prefix.
			sameLiterals := expectedLiterals[original.textStart]-expectedLiterals[expectedCursor] == storedLiterals[link.textStart]-storedLiterals[storedCursor]
			if original.target == link.target && sameLiterals && (!exactPrefix || original.textStart == expectedCursor+len(prefix)) &&
				compare(expectedText[expectedCursor:original.textStart], prefix) && slackExplicitLabelsMatch(original, link) {
				finishSuffix(original.textStart, link.textStart)
				pendingSuffix = nil
				matchedSpans = append(matchedSpans, [2]int{original.textStart, original.textEnd})
				expectedCursor, storedCursor = original.textEnd, link.textEnd
				explicitCursor++
				continue
			}
		}
		matched := false
		// Exact prefixes give the candidate directly, even if a message repeats
		// a domain many times in prose before Slack links its last occurrence.
		offset := expectedCursor
		candidateVerbatim := verbatimCursor
		if exactPrefix {
			offset += len(prefix)
		}
		for offset <= len(expectedText) && budget >= 0 {
			at := strings.Index(expectedText[offset:], rendered)
			if at < 0 {
				break
			}
			at += offset
			for candidateVerbatim < len(verbatim) && verbatim[candidateVerbatim][1] <= at {
				candidateVerbatim++
			}
			if candidateVerbatim < len(verbatim) && verbatim[candidateVerbatim][0] <= at && expectedText[verbatim[candidateVerbatim][0]] == '`' {
				offset = verbatim[candidateVerbatim][1]
				continue
			}
			sameLiterals := expectedLiterals[at]-expectedLiterals[expectedCursor] == storedLiterals[link.textStart]-storedLiterals[storedCursor]
			if sameLiterals && compare(expectedText[expectedCursor:at], prefix) {
				end := at + len(rendered)
				var nextSuffix *suffixCheck
				original := explicitCursor < len(explicit) && explicit[explicitCursor].textStart < end
				if original {
					if explicit[explicitCursor].textStart != at || explicit[explicitCursor].textEnd != end || explicit[explicitCursor].target != link.target {
						return false
					}
					explicitCursor++
				} else {
					_, authority, _ := strings.Cut(link.target, "://")
					hasPath := strings.IndexAny(authority, "/?#")
					if hasPath >= 0 {
						authority = authority[:hasPath]
					}
					for verbatimCursor < len(verbatim) && verbatim[verbatimCursor][1] <= at {
						verbatimCursor++
					}
					inVerbatim := verbatimCursor < len(verbatim) && verbatim[verbatimCursor][0] <= at
					if inVerbatim && (implicit || fullURI) && verbatim[verbatimCursor][0] < expectedCursor {
						// A previously matched link supplies its own end, even
						// when the URI regex extends across adjacent punctuation.
						// Scan only the unconsumed prefix to retain protection for
						// any new URI there without rescanning the remaining text.
						prefix := expectedText[expectedCursor:at]
						spans := slackVerbatimSpan.FindAllStringIndex(prefix, -1)
						inVerbatim = len(spans) > 0 && spans[len(spans)-1][1] == len(prefix) && prefix[spans[len(spans)-1][0]] != '`'
					}
					// Slack can leave an earlier URI unwrapped while linking
					// the next comma/semicolon-separated URL. Its already
					// matched prefix retains the earlier URI's literal text.
					if (implicit || fullURI) && slackReadbackSeparatorBefore(expectedText[expectedCursor:at]) {
						inVerbatim = false
					}
					// Email/reference spans can be embedded in the original
					// URI across earlier returned spans or punctuation. They
					// retain that URI's literal tail context.
					if (implicit && (strings.Contains(authority, "@") || slackAbsoluteLinkScheme.MatchString(link.label))) ||
						(inVerbatim && (implicit || fullURI) && (implicit || verbatim[verbatimCursor][0] != at)) {
						return false
					}
					if implicit && at > 0 && !markupEnds[at] {
						before, _ := utf8.DecodeLastRuneInString(expectedText[:at])
						if unicode.IsLetter(before) || unicode.IsNumber(before) || strings.ContainsRune(".-/@", before) {
							return false
						}
					}
					for suffixMarkupCursor < len(markup) && markup[suffixMarkupCursor][0] < end {
						suffixMarkupCursor++
					}
					limit := len(expectedText)
					if suffixMarkupCursor < len(markup) {
						limit = markup[suffixMarkupCursor][0]
					}
					// Check only the suffix before the next aligned link or
					// original markup span. Independent web links retain their
					// own rules; embedded mailto/reference spans may inherit URI
					// context during the forward scan. Each suffix is scanned once.
					tokenStart := at
					if inVerbatim {
						tokenStart = verbatim[verbatimCursor][0]
					}
					nextSuffix = &suffixCheck{
						linkStart: at, expectedStart: end, storedStart: link.textEnd,
						limit: limit, tokenStart: tokenStart, independent: implicit || fullURI, markup: suffixMarkupCursor < len(markup),
						optional: !implicit && !fullURI && !inVerbatim,
					}
				}
				finishSuffix(at, link.textStart)
				pendingSuffix = nextSuffix
				matchedSpans = append(matchedSpans, [2]int{at, end})
				expectedCursor, storedCursor = end, link.textEnd
				matched = true
				break
			}
			offset = at + len(rendered)
		}
		if !matched {
			return false
		}
	}
	if explicitCursor != len(explicit) || !compare(expectedText[expectedCursor:], storedText[storedCursor:]) {
		return false
	}
	finishSuffix(len(expectedText), len(storedText))
	if len(suffixes) == 0 {
		return true
	}
	// Verify each suffix as the prose scan reaches its link. Only the state
	// before that link can close formatting; literal URL tail characters are
	// excluded before scanning subsequent prose and links.
	nextIndependent := len(expectedText)
	for i := len(suffixes) - 1; i >= 0; i-- {
		p := suffixes[i]
		p.tokenLimit = min(p.limit, nextIndependent)
		if p.independent {
			nextIndependent = p.linkStart
		}
	}
	suffixCursor := 0
	carryEnd := -1
	checkSuffix := func(at int, state slackReadbackFormatting) (int, bool) {
		if suffixCursor == len(suffixes) || suffixes[suffixCursor].linkStart != at {
			return at, true
		}
		p := suffixes[suffixCursor]
		suffixCursor++
		if carryEnd <= at || p.independent {
			if p.optional {
				return at, true
			}
			// Scan the complete SOURCE token, across any returned link segments.
			// An embedded mention/email cannot turn a literal URI tail into prose.
			carryEnd = slackReadbackURLEnd(expectedText, p.tokenStart, p.tokenLimit, state)
		}
		literalEnd := max(p.expectedStart, min(carryEnd, p.expectedEnd))
		literal := expectedText[p.expectedStart:literalEnd]
		stored := storedText[p.storedStart:p.storedEnd]
		if !strings.HasPrefix(stored, literal) {
			return at, false
		}
		stored = stored[len(literal):]
		n, ok := slackReadbackProsePrefix(expectedText[literalEnd:p.expectedEnd], stored)
		return literalEnd, ok && (n == len(stored) ||
			(p.markup && p.expectedEnd == p.limit && storedMarkupStarts[p.storedStart+len(literal)+n]))
	}
	return slackReadbackFormattingMatches(expectedText, markup, matchedSpans, checkSuffix)
}

// Track surrounding mrkdwn delimiters in prose. Code/link markup and escaped
// markers do not change the surrounding formatting state. An opening marker
// needs a word boundary, so identifiers such as status_value remain literal.
func slackReadbackFormattingMatches(text string, markup, links [][2]int, checkSuffix func(int, slackReadbackFormatting) (int, bool)) bool {
	// Merge known boundaries, scanning only the intervening text for URI/code
	// tokens. A URI that Slack leaves unwrapped is just as literal as a link.
	var opaque [][2]int
	rawURI := make(map[int]bool)
	last := 0
	appendGap := func(end int) {
		if end > last {
			for _, span := range slackVerbatimSpan.FindAllStringIndex(text[last:end], -1) {
				opaque = append(opaque, [2]int{last + span[0], last + span[1]})
				if text[last+span[0]] != '`' {
					rawURI[last+span[0]] = true
				}
			}
		}
	}
	for m, l := 0, 0; m < len(markup) || l < len(links); {
		var span [2]int
		if l == len(links) || (m < len(markup) && markup[m][0] <= links[l][0]) {
			span = markup[m]
			m++
		} else {
			span = links[l]
			l++
		}
		appendGap(span[0])
		opaque = append(opaque, span)
		last = max(last, span[1])
	}
	appendGap(len(text))
	var state slackReadbackFormatting
	cursor, skipEnd := 0, 0
	for i := range len(text) {
		end, ok := checkSuffix(i, state)
		if !ok {
			return false
		}
		skipEnd = max(skipEnd, end)
		for cursor < len(opaque) && opaque[cursor][0] <= i {
			span := opaque[cursor]
			end := span[1]
			if rawURI[span[0]] {
				end = slackReadbackURLEnd(text, span[0], end, state)
			}
			skipEnd = max(skipEnd, end)
			cursor++
		}
		if i < skipEnd {
			continue
		}
		// Shortcode identifiers (including custom names) and Unicode
		// keycaps are atomic text, not formatting delimiters.
		if text[i] == ':' {
			if end := strings.IndexByte(text[i+1:], ':'); end >= 0 && slackEmojiShortcode.MatchString(strings.ToLower(text[i:i+end+2])) {
				skipEnd = i + end + 2
				continue
			}
		}
		bit, width := slackReadbackMarker(text, i)
		skipEnd = i + width
		if bit < 0 {
			continue
		}
		r, _ := utf8.DecodeRuneInString(text[i:])
		before, _ := utf8.DecodeLastRuneInString(text[:i])
		after, _ := utf8.DecodeRuneInString(text[i+width:])
		beforeWord := unicode.IsLetter(before) || unicode.IsNumber(before) || before == '_'
		if (state[bit] == width && !strings.ContainsRune("“‘«‹", r)) || strings.ContainsRune("”’»›", r) {
			state[bit] = 0
		} else if (bit >= 3 || !beforeWord) && !unicode.IsSpace(after) && i+width < len(text) {
			state[bit] = width
		}
	}
	return true
}

// A delimiter RUN is one delimiter: ** and __ must not toggle twice.
type slackReadbackFormatting [9]int

func slackReadbackSeparatorBefore(prefix string) bool {
	prefix = strings.TrimRight(prefix, "([{'\"“‘«‹")
	return strings.HasSuffix(prefix, ",") || strings.HasSuffix(prefix, ";")
}

// Return only actual formatting characters, excluding escapes, keycaps and
// apostrophes/underscores inside words. Paired quotes retain their own state.
func slackReadbackMarker(text string, at int) (int, int) {
	r, width := utf8.DecodeRuneInString(text[at:])
	bit := strings.IndexRune("*_~'\"", r)
	if bit < 0 {
		switch r {
		case '“', '”':
			bit = 5
		case '‘', '’':
			bit = 6
		case '«', '»':
			bit = 7
		case '‹', '›':
			bit = 8
		}
	}
	if bit < 0 || (r == '*' && slackEmojiUnitPrefix(text[at:]) > 0) || slackReadbackEscaped(text, at) {
		return -1, width
	}
	if bit < 3 {
		for at+width < len(text) && text[at+width] == byte(r) {
			width++
		}
	}
	if r == '_' || r == '\'' || r == '‘' || r == '’' {
		before, _ := utf8.DecodeLastRuneInString(text[:at])
		after, _ := utf8.DecodeRuneInString(text[at+width:])
		word := func(r rune) bool { return unicode.IsLetter(r) || unicode.IsNumber(r) || r == '_' }
		if word(before) && word(after) {
			return -1, width
		}
	}
	return bit, width
}

func slackReadbackEscaped(text string, at int) bool {
	return (at-len(strings.TrimRight(text[:at], `\`)))%2 != 0
}

func slackLiteralPrefixCounts(text string) []int {
	counts := make([]int, len(text)+1)
	for i := range len(text) {
		counts[i+1] = counts[i]
		// Neither shortcode/Unicode emoji folding nor expansion consumes
		// these ASCII separators; equality of their count is necessary.
		if strings.ContainsRune(" \t\r\n/@.,;()[]{}<>|=\\!?'\"", rune(text[i])) {
			counts[i+1]++
		}
	}
	return counts
}

func slackExplicitLabelsMatch(expected, stored slackReadbackLink) bool {
	if slackReferenceTarget.MatchString(expected.target) {
		return true // Reference identity is its already-verified target.
	}
	label := func(link slackReadbackLink) string {
		if link.labeled {
			return link.label
		}
		return strings.TrimPrefix(link.target, "mailto:")
	}
	return slackNormalizedPrefixesMatch(label(expected), label(stored))
}

// Find the source URL token's end once, independently of how many returned
// <url> / <url|label> segments cover it. The token is literal; everything after
// it is prose. Balanced path brackets, identifiers, quoted query values and
// internal/repeated formatting delimiters remain inside the token. Whitespace,
// original markup, unmatched closing brackets, an enclosing delimiter and
// trailing sentence punctuation/Unicode emoji end it.
//
// Slack documents auto-links and emoji conversion, but does not publish its
// complete URL lexer. These conservative boundaries pin that contract without
// treating Slack's returned link end alone as permission to fold URL bytes:
// https://docs.slack.dev/messaging/formatting-message-text/#links-in-retrieved-messages
func slackReadbackURLEnd(text string, start, limit int, state slackReadbackFormatting) int {
	for i := limit; i > start && limit < len(text); {
		r, width := utf8.DecodeLastRuneInString(text[start:i])
		i -= width
		if strings.ContainsRune(",;", r) {
			limit = i
			break
		}
		if !strings.ContainsRune("([{'\"“‘«‹", r) {
			break
		}
	}
	hardEnd := limit
	if n := strings.IndexFunc(text[start:limit], func(r rune) bool { return unicode.IsSpace(r) || strings.ContainsRune("<>|", r) }); n >= 0 {
		hardEnd = start + n
	}
	quoted := make(map[int]int)
	for _, span := range slackURIQuotedValue.FindAllStringIndex(text[start:hardEnd], -1) {
		quoted[start+span[0]+1] = start + span[1]
	}
	end := start
	var depth [3]int
	for end < hardEnd {
		if close := quoted[end]; close > 0 {
			end = close
			continue
		}
		r, width := utf8.DecodeRuneInString(text[end:hardEnd])
		if b := strings.IndexRune(")]}", r); b >= 0 {
			if depth[b] == 0 {
				break
			}
			depth[b]--
		} else if b := strings.IndexRune("([{", r); b >= 0 {
			depth[b]++
		}
		end += width
	}
	// Tokenize identifiers/emoji atomically before looking for trailing prose.
	// Otherwise an underscore in :white_check_mark: becomes a false closer.
	type unit struct {
		at, end, bit             int
		emoji, shortcode, quoted bool
	}
	var units []unit
	for i := start; i < end; {
		u := unit{at: i, bit: -1}
		if close := quoted[i]; close > 0 {
			u.end, u.quoted = close, true
		} else if n := slackEmojiUnitPrefix(text[i:end]); n > 0 {
			u.end, u.emoji, u.shortcode = i+n, true, text[i] == ':'
			if !u.shortcode {
				u.end = i + slackEmojiToneSuffix(text[i:end], n)
			}
		} else if text[i] == ':' {
			if n := strings.IndexByte(text[i+1:end], ':'); n >= 0 && slackEmojiShortcode.MatchString(strings.ToLower(text[i:i+n+2])) {
				u.end, u.shortcode = i+n+2, true
			}
		}
		if u.end == 0 {
			bit, width := slackReadbackMarker(text, i)
			u.end, u.bit = min(i+width, end), bit
		}
		units = append(units, u)
		i = u.end
	}
	boundary, proseTail, continuationAfter := end, true, false
	shortcodeAfter := false
	var later slackReadbackFormatting
	for i := len(units) - 1; i >= 0; i-- {
		u := units[i]
		switch {
		case u.quoted:
			proseTail, continuationAfter = false, true
		case u.emoji && !u.shortcode && proseTail && !continuationAfter && !shortcodeAfter:
			boundary, proseTail = u.at, true
		case u.shortcode:
			shortcodeAfter = true
			proseTail = proseTail && u.emoji
		case u.bit >= 0 && !strings.ContainsAny(text[u.at:u.end], "“‘«‹"):
			// A closer can have attached prose words. A marker that starts
			// a path segment or query value still belongs to the URI.
			segmentStart := u.at > start && strings.ContainsRune("/=", rune(text[u.at-1]))
			wordTail := !continuationAfter && !segmentStart
			if state[u.bit] == u.end-u.at && later[u.bit] == 0 && !(continuationAfter && segmentStart) && (proseTail || wordTail) {
				boundary, continuationAfter, shortcodeAfter = u.at, false, false
			} else {
				proseTail = false
			}
			later[u.bit]++
		case strings.ContainsRune(",;.!?", rune(text[u.at])) && proseTail:
			if text[u.at] != '?' || u.end == end || !units[i+1].shortcode {
				boundary = u.at
			}
		default:
			proseTail = false
		}
		// A query after an emoji is still URI content. Only a recognized
		// enclosing delimiter can move that query back into following prose.
		if strings.ContainsRune("/?#&=@", rune(text[u.at])) {
			continuationAfter = true
		}
	}
	// Host-adjacent :name: is prose for BOTH full and implicit URLs. A port
	// stays numeric; after a slash/query/fragment, typed shortcodes are literal.
	host := start
	if scheme := slackAbsoluteLinkScheme.FindString(text[start:end]); scheme != "" {
		host += len(scheme)
	}
	if strings.IndexAny(text[host:boundary], "/?#") >= 0 {
		return boundary
	}
	// Credentials and bracketed hosts stay literal before adjacent emoji.
	host += strings.LastIndexByte(text[host:boundary], '@') + 1
	for i := host; i < boundary; i++ {
		if i == host && text[i] == '[' {
			close := strings.IndexByte(text[i:boundary], ']')
			if close < 0 {
				return boundary
			}
			i += close
			continue
		}
		if text[i] == ':' && slackEmojiUnitPrefix(text[i:boundary]) > 0 {
			return i
		}
		if strings.ContainsRune(",;!([{'\"~=&", rune(text[i])) && i > host {
			return i
		}
	}
	return boundary
}

// Like the normal prose matcher, use the existing Unicode/shortcode units.
// At a URL boundary require each unit to be present: dropped/inserted suffixes
// must not make a changed link read back as delivered.
func slackReadbackProsePrefix(expected, stored string) (int, bool) {
	length := len(stored)
	for expected != "" {
		n, m := slackEmojiUnitPrefix(expected), slackEmojiUnitPrefix(stored)
		if n > 0 && m > 0 {
			// A typed tone after a Unicode unit is still present separately,
			// even if Slack appends an inherent tone to that unit's shortcode.
			if expected[0] != ':' {
				tone := expected[n:slackEmojiToneSuffix(expected, n)]
				if tone != "" && m > len(tone) && strings.HasSuffix(stored[:m], tone) {
					m -= len(tone)
				}
			}
			expected, stored = expected[n:], stored[m:]
			continue
		}
		_, width := utf8.DecodeRuneInString(expected)
		if !strings.HasPrefix(stored, expected[:width]) {
			return 0, false
		}
		expected, stored = expected[width:], stored[width:]
	}
	return length - len(stored), true
}

// Inputs have already had links/entities normalized exactly once.
func slackNormalizedPrefixesMatch(expected, stored string) bool {
	return expected == stored || slackFoldEmoji(expected) == slackFoldEmoji(stored) ||
		slackEmojiExpansionMatchesNormalized(expected, stored)
}

// The ordinary symmetric fold cannot resolve overlapping colon tokens:
// 10:30🎉 becomes 10:30:tada:, where an unknown :30: hides the emoji's opening
// colon. Reversing the scan instead breaks ✅ok: -> :white_check_mark:ok:.
// This fallback retains the posted text's literal boundaries and permits the
// same lossy emoji class as slackFoldEmoji only where that text had an emoji.
// Code and URI spans remain exact literals. It neither guesses which unknown
// token is an emoji nor discards changed timestamp/namespace/URL characters.
//
// Matching is a small finite-state walk: a literal consumes itself; an emoji
// consumes zero or more Unicode/standard-shortcode units. Memoization and the
// state budget bound ambiguous runs. Exhaustion retains the strict mismatch;
// ordinary symmetric matches never need this fallback.
// Test convenience wrapper; production matching enters slackReadbackTextMatches.
func slackEmojiExpansionMatches(expected, stored string) bool {
	return slackEmojiExpansionMatchesNormalized(slackNormalizeLinks(expected), slackNormalizeLinks(stored))
}

func slackEmojiExpansionMatchesNormalized(expected, stored string) bool {
	type part struct {
		literal string
		emoji   bool
	}
	var parts []part
	var literal strings.Builder
	flush := func() {
		if literal.Len() > 0 {
			parts = append(parts, part{literal: literal.String()})
			literal.Reset()
		}
	}
	prose := func(text string) {
		for len(text) > 0 {
			if n := slackEmojiUnitPrefix(text); n > 0 {
				flush()
				if len(parts) == 0 || !parts[len(parts)-1].emoji {
					parts = append(parts, part{emoji: true})
				}
				text = text[n:]
			} else {
				_, n := utf8.DecodeRuneInString(text)
				literal.WriteString(text[:n])
				text = text[n:]
			}
		}
	}
	last := 0
	for _, span := range slackVerbatimSpan.FindAllStringIndex(expected, -1) {
		prose(expected[last:span[0]])
		literal.WriteString(expected[span[0]:span[1]])
		last = span[1]
	}
	prose(expected[last:])
	flush()
	type state struct{ part, pos int }
	pending := []state{{}}
	seen := make(map[state]bool)
	const maxStates = 100000
	for len(pending) > 0 {
		at := pending[len(pending)-1]
		pending = pending[:len(pending)-1]
		if seen[at] {
			continue
		}
		if len(seen) >= maxStates {
			return false
		}
		seen[at] = true
		if at.part == len(parts) {
			if at.pos == len(stored) {
				return true
			}
			continue
		}
		p := parts[at.part]
		if p.emoji {
			if n := slackEmojiUnitPrefix(stored[at.pos:]); n > 0 {
				pending = append(pending, state{at.part, at.pos + n})
			}
			pending = append(pending, state{at.part + 1, at.pos})
		} else if strings.HasPrefix(stored[at.pos:], p.literal) {
			pending = append(pending, state{at.part + 1, at.pos + len(p.literal)})
		}
	}
	return false
}

// slackEmojiUnitPrefix consumes a unit at the current boundary only. Unknown
// colon tokens consume nothing, leaving their closing colon available when
// the caller advances through literal text one rune at a time.
func slackEmojiUnitPrefix(text string) int {
	if text == "" {
		return 0
	}
	if text[0] == ':' {
		if end := strings.IndexByte(text[1:], ':'); end >= 0 && slackIsStandardEmojiName(text[1:1+end]) {
			return slackEmojiToneSuffix(text, end+2)
		}
	}
	r, n := utf8.DecodeRuneInString(text)
	if r >= '0' && r <= '9' || r == '#' || r == '*' {
		end := n
		if strings.HasPrefix(text[end:], "\ufe0f") {
			end += len("\ufe0f")
		}
		if strings.HasPrefix(text[end:], "\u20e3") {
			return end + len("\u20e3")
		}
	}
	if !isSlackEmojiRune(r) {
		return 0
	}
	// Regional indicators form one flag; a ZWJ joins the following emoji
	// base into the same unit. Slack stores each such sequence as one name.
	if r >= 0x1F1E6 && r <= 0x1F1FF && n < len(text) {
		next, width := utf8.DecodeRuneInString(text[n:])
		if next >= 0x1F1E6 && next <= 0x1F1FF {
			n += width
		}
	}
	joined := false
	for n < len(text) {
		next, width := utf8.DecodeRuneInString(text[n:])
		if isEmojiSequenceGlue(next) {
			joined = joined || next == 0x200D
		} else if next >= 0x1F3FB && next <= 0x1F3FF {
			// A Unicode skin tone belongs to the preceding emoji base.
		} else if joined && isSlackEmojiRune(next) {
			joined = false
		} else {
			break
		}
		n += width
	}
	return n
}

// Slack represents a toned emoji with a base shortcode plus a tone shortcode.
func slackEmojiToneSuffix(text string, n int) int {
	for strings.HasPrefix(text[n:], ":skin-tone-") {
		end := strings.IndexByte(text[n+1:], ':')
		if end < 0 || !slackIsStandardEmojiName(text[n+1:n+1+end]) {
			break
		}
		n += end + 2
	}
	return n
}
