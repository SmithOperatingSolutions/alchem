package syntax

import "testing"

func TestActorTypeErrors(t *testing.T) {
	for _, body := range []string{
		`p: pid[fn[integer]] = Process.self(1)`,
		`p: pid[integer] = Process.self(1) Process.send(p,true,0)`,
		`p = Process.spawn(fn(): integer do return 0 end,1)`,
		`p = Process.spawn(fn(self: pid[integer]): boolean do return true end,1)`,
		`Process.loop(0,fn(): integer do return 0 end)`, `Process.loop(0,fn(n: integer): integer do return n end)`, `Process.loop(true,fn(n: integer): tuple[boolean,integer] do return {true,n} end)`, `Process.receive(1,0)`, `Process.monitor(true)`, `Process.event(true)`,
		`Supervisor.start("one_for_one",1,1000,[{"child","permanent",fn(): integer do return 0 end}],1)`,
		`Process.unknown()`, `Supervisor.child(1,"name")`,
	} {
		t.Run(body, func(t *testing.T) {
			if _, err := Parse("defmodule A do def main() do " + body + " end end"); err == nil {
				t.Fatal("accepted invalid runtime call")
			}
		})
	}
}

func TestLoopTypes(t *testing.T) {
	if _, err := Parse(`defmodule A do def main() do result=Process.loop(0,fn(n: integer): tuple[boolean,integer] do return {n<2,n+1} end) assert(result==3) end end`); err != nil {
		t.Fatal(err)
	}
}
