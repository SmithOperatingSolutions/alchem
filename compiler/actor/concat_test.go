package actor

import (
	"strings"
	"testing"
)

// Growing a string must give the same text as plain concatenation, and no
// string taken along the way may change, whichever of them is extended next.
func TestConcatNeverChangesExistingStrings(t *testing.T) {
	c := &Context{}
	piece := "0123456789"
	acc, want := "", ""
	var kept, expected []string
	for i := 0; i < 400; i++ {
		acc = Concat(c, acc, piece[i%7:])
		want += piece[i%7:]
		if acc != want {
			t.Fatalf("step %d: got %q want %q", i, acc, want)
		}
		kept = append(kept, acc)
		expected = append(expected, strings.Clone(want))
		if i%9 == 0 {
			// Branch off an older string, then go on from the newest.
			older := kept[len(kept)/2]
			branch := Concat(c, older, "BRANCH")
			if branch != expected[len(kept)/2]+"BRANCH" {
				t.Fatalf("step %d: branch %q", i, branch)
			}
			again := Concat(c, branch, "!")
			if again != expected[len(kept)/2]+"BRANCH!" || branch != expected[len(kept)/2]+"BRANCH" {
				t.Fatalf("step %d: extending the branch changed it", i)
			}
		}
		if i%13 == 0 {
			// Two extensions of the same string must not see each other.
			left, right := Concat(c, acc, "L"), Concat(c, acc, "R")
			if left != want+"L" || right != want+"R" || acc != want {
				t.Fatalf("step %d: %q %q", i, left, right)
			}
		}
	}
	for i, text := range kept {
		if text != expected[i] {
			t.Fatalf("string %d changed after later concatenations", i)
		}
	}
	// A part of the string that is itself extended overlaps the buffer.
	whole := Concat(c, strings.Repeat("a", 40), strings.Repeat("b", 40))
	whole = Concat(c, whole, "c")
	doubled := Concat(c, whole, whole[10:50])
	if doubled != strings.Repeat("a", 40)+strings.Repeat("b", 40)+"c"+strings.Repeat("a", 30)+strings.Repeat("b", 10) {
		t.Fatalf("self-append: %q", doubled)
	}
	if Concat(c, "", "x") != "x" || Concat(c, "x", "") != "x" {
		t.Fatal("empty operands")
	}
}

// Another process holding a string keeps reading it while the builder goes
// on extending the shared buffer; the race detector checks the claim that
// they never touch the same bytes.
func TestConcatSharedAcrossGoroutines(t *testing.T) {
	c := &Context{}
	acc := strings.Repeat("s", 64)
	done := make(chan int)
	readers := 0
	for i := 0; i < 200; i++ {
		acc = Concat(c, acc, "abcdefgh")
		if i%20 == 0 {
			readers++
			go func(text string, length int) {
				total := 0
				for round := 0; round < 50; round++ {
					total += strings.Count(text, "a")
				}
				if len(text) != length {
					total = -1
				}
				done <- total
			}(acc, len(acc))
		}
	}
	for i := 0; i < readers; i++ {
		if <-done < 0 {
			t.Fatal("a shared string changed length")
		}
	}
}
