package syntax

import (
	"fmt"
	"github.com/SmithOperatingSolutions/alchem/compiler/ast"
)

func (c checker) actorBuiltin(e *ast.Expr, scope map[string]string, want string) (string, error) {
	fail := func(s string) (string, error) { return "", diagnostic(e.Line, e.Column, "%s", s) }
	counts := map[string]int{"Process.self": 1, "Process.loop": 2, "Process.spawn": 2, "Process.send": 3, "Process.receive": 2, "Process.await": 2, "Process.stop": 1, "Process.alive": 1, "Process.id": 1, "Process.monitor": 1, "Process.demonitor": 2, "Process.link": 1, "Process.unlink": 1, "Process.trap_exits": 1, "Process.event": 1, "Process.sleep": 1, "Process.crash": 1, "Process.report": 1, "Supervisor.start": 5, "Supervisor.start_link": 5, "Supervisor.child": 2, "Supervisor.stop": 2, "Supervisor.await": 2, "Supervisor.alive": 1, "Supervisor.restarts": 1, "Supervisor.children": 1}
	count, ok := counts[e.Name]
	if !ok {
		return fail("unknown runtime operation " + e.Name)
	}
	if len(e.Args) != count {
		return fail(fmt.Sprintf("%s requires %d arguments", e.Name, count))
	}
	arg := func(i int, typ string) (string, error) { return c.expr(e.Args[i], scope, typ) }
	switch e.Name {
	case "Process.loop":
		callback, err := arg(1, "")
		if err != nil {
			return "", err
		}
		params, result, ok := ast.FunctionParts(callback)
		if !ok || len(params) != 1 {
			return fail("loop callback must accept one state argument")
		}
		parts, ok := ast.TupleElements(result)
		if !ok || len(parts) != 2 || parts[0] != "boolean" || parts[1] != params[0] {
			return fail("loop callback must return tuple[boolean,State]")
		}
		if _, err = arg(0, params[0]); err != nil {
			return "", err
		}
		return params[0], nil
	case "Process.self":
		msg, ok := ast.CapabilityElement(want, "pid")
		if !ok {
			return fail("Process.self requires an expected pid[T] type")
		}
		if !c.sendable(msg) {
			return fail("mailbox messages cannot contain functions")
		}
		if _, err := arg(0, "integer"); err != nil {
			return "", err
		}
		return want, nil
	case "Process.spawn":
		t, err := arg(0, "")
		if err != nil {
			return "", err
		}
		params, result, ok := ast.FunctionParts(t)
		if !ok || len(params) != 1 || result != "integer" {
			return fail("spawn callback must be fn[pid[T],integer]")
		}
		msg, ok := ast.CapabilityElement(params[0], "pid")
		if !ok || !c.sendable(msg) {
			return fail("spawn requires a sendable pid[T] callback argument")
		}
		if _, err = arg(1, "integer"); err != nil {
			return "", err
		}
		return "pid[" + msg + "]", nil
	case "Process.sleep", "Process.event":
		if _, err := arg(0, "integer"); err != nil {
			return "", err
		}
		if e.Name == "Process.event" {
			return "tuple[boolean,integer,integer,string]", nil
		}
		return "integer", nil
	case "Process.crash":
		if _, err := arg(0, "string"); err != nil {
			return "", err
		}
		return "integer", nil
	case "Process.trap_exits":
		if _, err := arg(0, "boolean"); err != nil {
			return "", err
		}
		return "boolean", nil
	}
	if e.Name == "Supervisor.start" || e.Name == "Supervisor.start_link" {
		if _, err := arg(0, "string"); err != nil {
			return "", err
		}
		for _, i := range []int{1, 2, 4} {
			if _, err := arg(i, "integer"); err != nil {
				return "", err
			}
		}
		specs, err := arg(3, "")
		if err != nil {
			return "", err
		}
		element, ok := ast.ListElement(specs)
		if !ok {
			return fail("supervisor requires a nonempty typed child-spec list")
		}
		parts, ok := ast.TupleElements(element)
		if !ok || len(parts) != 3 || parts[0] != "string" || parts[1] != "string" {
			return fail("child spec is tuple[string,string,fn[pid[T],integer]]")
		}
		params, result, ok := ast.FunctionParts(parts[2])
		if !ok || len(params) != 1 || result != "integer" {
			return fail("invalid child callback")
		}
		msg, ok := ast.CapabilityElement(params[0], "pid")
		if !ok {
			return fail("child callback requires pid[T]")
		}
		return "supervisor[" + msg + "]", nil
	}
	target, err := arg(0, "")
	if err != nil {
		return "", err
	}
	if len(e.Name) >= 11 && e.Name[:11] == "Supervisor." {
		msg, ok := ast.CapabilityElement(target, "supervisor")
		if !ok {
			return fail("operation requires supervisor[T]")
		}
		switch e.Name {
		case "Supervisor.child":
			if _, err = arg(1, "string"); err != nil {
				return "", err
			}
			return "pid[" + msg + "]", nil
		case "Supervisor.stop", "Supervisor.await":
			if _, err = arg(1, "integer"); err != nil {
				return "", err
			}
			if e.Name == "Supervisor.await" {
				return "tuple[boolean,string]", nil
			}
			return "boolean", nil
		case "Supervisor.alive":
			return "boolean", nil
		case "Supervisor.restarts":
			return "integer", nil
		default:
			return "list[tuple[string,integer]]", nil
		}
	}
	msg, ok := ast.CapabilityElement(target, "pid")
	if !ok {
		return fail("operation requires pid[T]")
	}
	switch e.Name {
	case "Process.send":
		if _, err = arg(1, msg); err != nil {
			return "", err
		}
		if _, err = arg(2, "integer"); err != nil {
			return "", err
		}
		return "boolean", nil
	case "Process.receive", "Process.await":
		if _, err = arg(1, "integer"); err != nil {
			return "", err
		}
		if e.Name == "Process.receive" {
			return "tuple[boolean," + msg + "]", nil
		}
		return "tuple[boolean,string]", nil
	case "Process.id", "Process.monitor":
		return "integer", nil
	case "Process.report":
		return "string", nil
	case "Process.demonitor":
		if _, err = arg(1, "integer"); err != nil {
			return "", err
		}
	}
	return "boolean", nil
}
