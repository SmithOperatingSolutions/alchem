package actor

import "runtime"

// Depth returns the current call depth, to be restored if a failure raised
// below this point is rescued: a failure unwinds without counting back down.
func Depth(c *Context) int64 { return c.depth }

// Rescue decides whether a recovered panic is a failure the program may
// handle, and returns its message. A request to stop the process is not: it
// must keep unwinding. depth is the call depth to resume at.
func Rescue(c *Context, value any, depth int64) (string, bool) {
	if _, stopping := value.(exit); stopping {
		return "", false
	}
	message, _ := recovered(value)
	c.depth = depth
	return message, true
}

// Handling enters (+1) or leaves (-1) a try whose rescue takes every
// failure. While inside one, a failure is certain to be handled by the
// program, so Fail does not record the stack it would otherwise report.
func Handling(c *Context, change int64) { c.handled += change }

// Thrown carries a value given to throw up to the try that catches it.
type Thrown struct {
	Value any
	Where string
}

// Throw unwinds with a value for a catch arm.
func Throw(c *Context, where string, value any) {
	Check(c)
	panic(Thrown{Value: value, Where: where})
}

// Raise fails the process with an exception value and its message.
func Raise(c *Context, where string, raised any, message string) {
	f := &Failure{Where: where, Message: message, Raised: raised, names: c.rt.names}
	if c.handled == 0 {
		var pcs [64]uintptr
		f.pcs = append(f.pcs, pcs[:runtime.Callers(2, pcs[:])]...)
	}
	panic(f)
}

// Rescued decides whether a recovered panic is a failure a rescue arm may
// handle, and returns its message and exception value, if it was raised
// with one. A stop request and a thrown value are not failures.
func Rescued(c *Context, value any, depth int64) (string, any, bool) {
	switch value.(type) {
	case exit, Thrown:
		return "", nil, false
	}
	message, f := recovered(value)
	c.depth = depth
	var raised any
	if f != nil {
		raised = f.Raised
	}
	return message, raised, true
}

// Caught returns the value of a recovered throw.
func Caught(c *Context, value any, depth int64) (any, bool) {
	thrown, ok := value.(Thrown)
	if !ok {
		return nil, false
	}
	c.depth = depth
	return thrown.Value, true
}
