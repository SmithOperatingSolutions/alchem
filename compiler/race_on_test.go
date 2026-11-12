//go:build race

package compiler

// raceDetector is set when the tests run under the race detector, which
// makes the long checks of single-threaded code not worth their time.
const raceDetector = true
