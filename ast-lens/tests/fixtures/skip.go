// Package skipme is large enough to cross the outline threshold but
// carries an outline:skip directive in its header, so the emitter must
// fall back to passthrough (empty output) regardless of size.
package skipme

import (
	"fmt"
	"strings"
)

// Widget is an exported type that would normally appear in an outline.
type Widget struct {
	Name  string
	Count int
}

// NewWidget constructs a Widget with the supplied name.
func NewWidget(name string) *Widget {
	return &Widget{Name: name}
}

// Render returns a human-readable form of the widget.
func (w *Widget) Render() string {
	return fmt.Sprintf("%s x%d", w.Name, w.Count)
}

// Bump increments the widget's count by n.
func (w *Widget) Bump(n int) {
	w.Count += n
}

// Reset returns the widget's count to zero.
func (w *Widget) Reset() {
	w.Count = 0
}

// Join concatenates widget names with a separator.
func Join(widgets []*Widget, sep string) string {
	names := make([]string, 0, len(widgets))
	for _, w := range widgets {
		names = append(names, w.Name)
	}
	return strings.Join(names, sep)
}

// Filter returns widgets whose count exceeds the threshold.
func Filter(widgets []*Widget, min int) []*Widget {
	out := make([]*Widget, 0, len(widgets))
	for _, w := range widgets {
		if w.Count > min {
			out = append(out, w)
		}
	}
	return out
}

// Total sums the counts across all widgets.
func Total(widgets []*Widget) int {
	sum := 0
	for _, w := range widgets {
		sum += w.Count
	}
	return sum
}

// Largest returns the widget with the highest count, or nil.
func Largest(widgets []*Widget) *Widget {
	var best *Widget
	for _, w := range widgets {
		if best == nil || w.Count > best.Count {
			best = w
		}
	}
	return best
}

// Names extracts the names of all widgets in order.
func Names(widgets []*Widget) []string {
	out := make([]string, 0, len(widgets))
	for _, w := range widgets {
		out = append(out, w.Name)
	}
	return out
}

// CountByName builds a name to count lookup table.
func CountByName(widgets []*Widget) map[string]int {
	out := make(map[string]int, len(widgets))
	for _, w := range widgets {
		out[w.Name] = w.Count
	}
	return out
}

// Clone returns a deep copy of the widget slice.
func Clone(widgets []*Widget) []*Widget {
	out := make([]*Widget, 0, len(widgets))
	for _, w := range widgets {
		cp := *w
		out = append(out, &cp)
	}
	return out
}

// describe is a private helper formatting widget internals.
func describe(w *Widget) string {
	return fmt.Sprintf("Widget{Name:%q Count:%d}", w.Name, w.Count)
}

// indexByName builds a private reverse index of widgets by name.
func indexByName(widgets []*Widget) map[string]*Widget {
	out := make(map[string]*Widget, len(widgets))
	for _, w := range widgets {
		out[w.Name] = w
	}
	return out
}

// sortKey is a private helper returning a stable sort key for a widget.
func sortKey(w *Widget) string {
	return strings.ToLower(w.Name)
}

// validateName is a private helper enforcing the name format.
func validateName(name string) error {
	if name == "" {
		return fmt.Errorf("skipme: empty name")
	}
	return nil
}

// dedupe is a private helper removing widgets with duplicate names.
func dedupe(widgets []*Widget) []*Widget {
	seen := make(map[string]bool)
	out := make([]*Widget, 0, len(widgets))
	for _, w := range widgets {
		if seen[w.Name] {
			continue
		}
		seen[w.Name] = true
		out = append(out, w)
	}
	return out
}

// partition splits widgets into matching and non-matching slices.
func partition(widgets []*Widget, min int) (hi, lo []*Widget) {
	for _, w := range widgets {
		if w.Count >= min {
			hi = append(hi, w)
		} else {
			lo = append(lo, w)
		}
	}
	return hi, lo
}

// maxName returns the lexicographically greatest widget name.
func maxName(widgets []*Widget) string {
	best := ""
	for _, w := range widgets {
		if w.Name > best {
			best = w.Name
		}
	}
	return best
}

// minCount returns the smallest count among widgets, or zero.
func minCount(widgets []*Widget) int {
	if len(widgets) == 0 {
		return 0
	}
	m := widgets[0].Count
	for _, w := range widgets[1:] {
		if w.Count < m {
			m = w.Count
		}
	}
	return m
}

// averageCount returns the mean count across widgets.
func averageCount(widgets []*Widget) float64 {
	if len(widgets) == 0 {
		return 0
	}
	return float64(Total(widgets)) / float64(len(widgets))
}

// formatAll renders every widget on its own line.
func formatAll(widgets []*Widget) string {
	var b strings.Builder
	for _, w := range widgets {
		b.WriteString(describe(w))
		b.WriteByte('\n')
	}
	return b.String()
}

// totalNameLen is a private helper summing the length of all names.
func totalNameLen(widgets []*Widget) int {
	n := 0
	for _, w := range widgets {
		n += len(w.Name)
	}
	return n
}

// hasName reports whether any widget carries the given name.
func hasName(widgets []*Widget, name string) bool {
	for _, w := range widgets {
		if w.Name == name {
			return true
		}
	}
	return false
}
