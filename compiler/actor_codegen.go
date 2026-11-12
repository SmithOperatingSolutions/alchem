package compiler

import (
	"github.com/SmithOperatingSolutions/alchem/compiler/ast"
	"strings"
)

func (g *generator) actorCall(e *ast.Expr, scope map[string]string) string {
	args := []string{"ctx"}
	for _, arg := range e.Args {
		args = append(args, g.expr(arg, scope))
	}
	where := g.location(e.Line, e.Column)
	names := map[string]string{"Process.loop": "Loop", "Process.spawn": "Spawn", "Process.send": "Send", "Process.receive": "Receive", "Process.await": "Await", "Process.stop": "Stop", "Process.alive": "Alive", "Process.id": "ID", "Process.monitor": "Monitor", "Process.demonitor": "Demonitor", "Process.link": "Link", "Process.unlink": "Unlink", "Process.trap_exits": "Trap", "Process.event": "NextEvent", "Process.sleep": "Sleep", "Process.crash": "Crash", "Process.report": "Report", "Supervisor.start": "StartSupervisor", "Supervisor.start_link": "StartLinkedSupervisor", "Supervisor.child": "Child", "Supervisor.stop": "StopSupervisor", "Supervisor.await": "AwaitSupervisor", "Supervisor.alive": "SupervisorAlive", "Supervisor.restarts": "Restarts", "Supervisor.children": "Children"}
	if e.Name == "Process.self" {
		elem, _ := ast.CapabilityElement(e.Type, "pid")
		return "actor.Self[" + goType(elem) + "](" + strings.Join(append(args, where), ",") + ")"
	}
	if e.Name != "Process.event" && e.Name != "Process.trap_exits" {
		args = append(args, where)
	}
	// The runtime API speaks Go slices in list order; convert at the boundary.
	if e.Name == "Supervisor.start" || e.Name == "Supervisor.start_link" {
		args[4] = "fwd(" + args[4] + ")"
	}
	call := "actor." + names[e.Name] + "(" + strings.Join(args, ",") + ")"
	if e.Name == "Supervisor.children" {
		return "mk(" + call + ")"
	}
	if _, ok := ast.TupleElements(e.Type); ok {
		return goType(e.Type) + "(" + call + ")"
	}
	return call
}
