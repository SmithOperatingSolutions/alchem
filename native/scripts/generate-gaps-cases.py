#!/usr/bin/env python3
"""Regenerate harness/gaps-cases.json.xz: the programs of the gaps gate with
what the pinned compiler makes of each. Not used by normal builds.

The programs are the probes behind the differences closed in
spec/alchem-closures.md ("Where a lambda takes its types"),
spec/alchem-generics.md, spec/alchem-operators.md ("Bitwise operators"),
spec/source-capacity.md ("Fixed limits") and spec/alchem-library-profile.md:

- lambdas in every position a type is expected (lambdas()), and lambda
  bodies whose own type is under-determined (bodies());
- programs at and past each fixed limit the native compiler had, and at
  sizes of a few thousand (limits());
- the hand-written probes of harness/gaps-hand.json.xz.

Every program is run by build/dev/alchem-upstream (the pinned compiler
behind its memory and time ceiling; its answers are kept in
build/dev/gaps-upstream.json) and compiled by build/dev/A2. A case is the
source, then the status, standard output and standard error of the run with
the file named <stdin>; a program the pinned compiler rejects has status
null. Only programs the native compiler agrees on are written, since the
gate has to pass; the others are printed, and spec/source-capacity.md and
the specs above say why each remains. The native compiler is given 1 GB and
a minute for each, so that the gate can run eight at a time: a program that
needs more is printed as one that differs."""
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import hashlib
import itertools
import json
import lzma
import os
import subprocess
import sys
import tempfile

ROOT=Path(__file__).resolve().parents[1]
UPSTREAM=ROOT/'build/dev/alchem-upstream'
NATIVE=ROOT/'build/dev/A2'
ENV=dict(os.environ,GOTOOLCHAIN='local',GOPROXY='off',GOFLAGS='-mod=mod',GOMODCACHE=str(ROOT/'.cache/gomod'))


def lambdas():
    P=[]
    F="fn[integer, integer]"
    lams={
     'u':("fn x -> x + n end","fn y -> y * 2 end"),
     'c':("&(&1 + n)","&(&1 * 2)"),
     't':("fn(x: integer): integer do x + n end","fn y -> y * 2 end"),
     'ut':("fn x -> x + n end","fn(y: integer): integer do y * 2 end"),
     'r':("&inc/1","fn y -> y * 2 end"),
     'ur':("fn x -> x + n end","&inc/1"),
     'w':("fn _ -> n end","fn y -> y end"),
     'b':("fn x ->\n      z = x + n\n      z\n    end","&(&1 * 2)"),
    }
    vctx={
     'id':lambda a,b:a,
     'par':lambda a,b:"("+a+")",
     'if':lambda a,b:"if n > 0 do "+a+" else "+b+" end",
     'case':lambda a,b:"case n do\n      0 -> "+b+"\n      _ -> "+a+"\n    end",
     'cond':lambda a,b:"cond do\n      n > 0 -> "+a+"\n      true -> "+b+"\n    end",
    }
    wraps={
     'id':(lambda a,b:a, F, lambda v: v+".(3)"),
     'list':(lambda a,b:"["+a+", "+b+"]", "list["+F+"]", lambda v:"Enum.map("+v+", fn g -> g.(3) end)"),
     'list1':(lambda a,b:"["+a+"]", "list["+F+"]", lambda v:"Enum.map("+v+", fn g -> g.(3) end)"),
     'tuple':(lambda a,b:"{"+a+", 1}", "tuple["+F+", integer]", lambda v:"elem("+v+", 0).(3)"),
     'tuple2':(lambda a,b:"{1, "+a+", "+b+"}", "tuple[integer, "+F+", "+F+"]", lambda v:"elem("+v+", 2).(3)"),
     'map':(lambda a,b:'%{"a" => '+a+', "b" => '+b+'}', "map[string, "+F+"]", lambda v:'Map.fetch!('+v+', "a").(3)'),
     'struct':(lambda a,b:'%Op{name: "x", run: '+a+'}', "Op", lambda v:v+'.run.(3)'),
     'nest':(lambda a,b:"[{1, "+a+"}, {2, "+b+"}]", "list[tuple[integer, "+F+"]]", lambda v:"Enum.map("+v+", fn {i, g} -> g.(i) end)"),
    }
    def prog(defs, body):
        return ("defmodule Main do\n  struct Op do\n    name: string\n    run: "+F+"\n  end\n  def inc(x: integer): integer do x + 1 end\n"+defs+
                "  def main() do\n    n = 5\n"+"".join("    "+l+"\n" for l in body.split("\n"))+"  end\nend\n")
    sinks={}
    def s_ann(E,T,use): return prog("", "v: "+T+" = "+E+"\nIO.inspect("+use("v")+")")
    def s_un(E,T,use): return prog("", "v = "+E+"\nIO.inspect("+use("v")+")")
    def s_arg(E,T,use): return prog("  def use(v: "+T+"): integer do\n    IO.inspect("+use("v")+")\n    0\n  end\n", "IO.inspect(use("+E+"))")
    def s_ret(E,T,use): return prog("  def mk(n: integer): "+T+" do\n    "+E+"\n  end\n", "v = mk(n)\nIO.inspect("+use("v")+")")
    def s_retif(E,T,use): return prog("  def mk(n: integer): "+T+" do\n    if n > 100 do\n      "+E+"\n    else\n      "+E+"\n    end\n  end\n", "v = mk(n)\nIO.inspect("+use("v")+")")
    def s_pipe(E,T,use): return prog("  def use(v: "+T+"): integer do\n    IO.inspect("+use("v")+")\n    0\n  end\n", "IO.inspect("+E+" |> use())")
    def s_inline(E,T,use): return prog("", "IO.inspect("+use("("+E+")")+")")
    def s_lam(E,T,use): return prog("", "h: fn[integer, "+T+"] = fn k -> "+E+" end\nv = h.(1)\nIO.inspect("+use("v")+")")
    def s_gen(E,T,use): return prog("  def gid(x: t): t do x end\n", "v: "+T+" = gid("+E+")\nIO.inspect("+use("v")+")")
    sinks=dict(ann=s_ann,un=s_un,arg=s_arg,ret=s_ret,retif=s_retif,pipe=s_pipe,inline=s_inline,lam=s_lam,gen=s_gen)

    for index,((ln,(a,b)),(vn,vc),(wn,(w,T,use)),(sn,s)) in enumerate(itertools.product(lams.items(),vctx.items(),wraps.items(),sinks.items())):
        if index%9==0:P.append(s(w(vc(a,b),b),T,use))
    return P


def bodies():
    P=[]
    # result types with bodies (expression using parameter x: integer)
    R={
     'opt':("option[integer]",["none","some(x)","if x > 0 do none else some(x) end","if x > 0 do some(x) else none end","case x do\n      0 -> none\n      _ -> some(x)\n    end","Integer.parse(\"z\") |> elem_or(x)"]),
     'lst':("list[integer]",["[]","[x]","if x > 0 do [] else [x] end","if x > 0 do [x] else [] end","[] ++ []","Enum.filter([], fn y -> y > x end)","tl([x])"]),
     'map':("map[string, integer]",["%{}","%{\"a\" => x}","if x > 0 do %{} else %{\"a\" => x} end","Map.new([])"]),
     'res':("result[integer, string]",["ok(x)","error(\"e\")","if x > 0 do ok(x) else error(\"e\") end","if x > 0 do error(\"e\") else ok(x) end"]),
     'tup':("tuple[option[integer], list[string]]",["{none, []}","{some(x), []}","{none, [\"a\"]}","if x > 0 do {none, []} else {some(x), [\"a\"]} end"]),
     'lopt':("list[option[integer]]",["[]","[none]","[none, some(x)]","[some(x), none]"]),
     'fnr':("fn[integer, option[integer]]",["fn _ -> none end","fn y -> some(y + x) end","fn(y: integer): option[integer] do none end","if x > 0 do fn _ -> none end else fn y -> some(y) end end"]),
     'unit':("tuple[]",["{}","IO.puts(\"side\")"]),
     'int':("integer",["x","raise \"boom\"","if x > 0 do raise \"boom\" else x end"]),
    }
    def prog(defs, body):
        return ("defmodule Main do\n  def elem_or(r: result[tuple[integer, string], string], x: integer): option[integer] do\n    case r do\n      ok(t) -> some(elem(t, 0))\n      error(_) -> none\n    end\n  end\n"+defs+
                "  def main() do\n"+"".join("    "+l+"\n" for l in body.split("\n"))+"  end\nend\n")
    def show(T, v):
        if T.startswith("fn["): return "IO.inspect("+v+".(2))"
        return "IO.inspect("+v+")"
    C={}
    C['param']=lambda T,b: prog("  def ap(f: fn[integer, "+T+"]): "+T+" do f.(0) end\n", "r = ap(fn x -> "+b+" end)\n"+show(T,"r"))
    C['ann']=lambda T,b: prog("", "f: fn[integer, "+T+"] = fn x -> "+b+" end\nr = f.(0)\n"+show(T,"r"))
    C['ret']=lambda T,b: prog("  def mk(): fn[integer, "+T+"] do\n    fn x -> "+b+" end\n  end\n", "r = mk().(0)\n"+show(T,"r"))
    C['invoke']=lambda T,b: prog("", "ap = fn(f: fn[integer, "+T+"]): "+T+" do f.(0) end\nr = ap.(fn x -> "+b+" end)\n"+show(T,"r"))
    C['field']=lambda T,b: prog("  struct H do\n    run: fn[integer, "+T+"]\n  end\n", "h = %H{run: fn x -> "+b+" end}\nr = h.run.(0)\n"+show(T,"r"))
    C['list']=lambda T,b: prog("", "l: list[fn[integer, "+T+"]] = [fn x -> "+b+" end, fn x -> "+b+" end]\nr = hd(l).(0)\n"+show(T,"r"))
    C['gen_ann']=lambda T,b: prog("  def gap(f: fn[a, b], x: a): b do f.(x) end\n", "r: "+T+" = gap(fn x -> "+b+" end, 0)\n"+show(T,"r"))
    C['gen_late']=lambda T,b: prog("  def gap(x: a, f: fn[a, b]): b do f.(x) end\n", "r = gap(0, fn x -> "+b+" end)\n"+show(T,"r"))
    C['gen_late_ann']=lambda T,b: prog("  def gap(x: a, f: fn[a, b]): b do f.(x) end\n", "r: "+T+" = gap(0, fn x -> "+b+" end)\n"+show(T,"r"))
    C['map_ann']=lambda T,b: prog("", "r: list["+T+"] = Enum.map([0, 1], fn x -> "+b+" end)\n"+("IO.inspect(length(r))" if T.startswith("fn[") else "IO.inspect(r)"))
    C['map_un']=lambda T,b: prog("", "r = Enum.map([0, 1], fn x -> "+b+" end)\n"+("IO.inspect(length(r))" if T.startswith("fn[") else "IO.inspect(r)"))
    C['two']=lambda T,b: prog("  def ap(f: fn[integer, string, "+T+"]): "+T+" do f.(0, \"s\") end\n", "r = ap(fn x, _ -> "+b+" end)\n"+show(T,"r"))
    C['nested']=lambda T,b: prog("  def ap(f: fn[integer, fn[integer, "+T+"]]): "+T+" do f.(5).(0) end\n", "r = ap(fn _ -> fn x -> "+b+" end end)\n"+show(T,"r"))
    C['ret_early']=lambda T,b: prog("  def ap(f: fn[integer, "+T+"]): "+T+" do f.(0) end\n", "r = ap(fn x ->\n  if x > 5 do return "+b.split("\n")[0]+" end\n  "+b+"\nend)\n"+show(T,"r"))
    C['block']=lambda T,b: prog("  def ap(f: fn[integer, "+T+"]): "+T+" do f.(0) end\n", "r = ap(fn x ->\n  y = x + 1\n  IO.puts(\"in\")\n  "+b.replace("x","y")+"\nend)\n"+show(T,"r"))
    C['pipe']=lambda T,b: prog("  def ap(x: integer, f: fn[integer, "+T+"]): "+T+" do f.(x) end\n", "r = 0 |> ap(fn x -> "+b+" end)\n"+show(T,"r"))
    C['reduce']=lambda T,b: prog("", "r = Enum.reduce([0, 1], "+b.split("\n")[0].replace("x","7")+", fn x, _ -> "+b+" end)\n"+show(T,"r"))
    C['reduce_ann']=lambda T,b: prog("", "r: "+T+" = Enum.reduce([0, 1], "+b.split("\n")[0].replace("x","7")+", fn x, _ -> "+b+" end)\n"+show(T,"r"))
    C['mapupd']=lambda T,b: prog("", "m: map[string, "+T+"] = %{}\nr = Map.update(m, \"k\", "+b.split("\n")[0].replace("x","7")+", fn _ -> "+b.replace("x","7")+" end)\nIO.inspect(map_size(r))")

    for (rn,(T,texts)),(cn,c) in itertools.product(R.items(),C.items()):
        for i,b in enumerate(texts):
            if cn in('ret_early','reduce','reduce_ann','mapupd') and ("\n" in b or b.startswith("IO.") or b.startswith("raise") or b.startswith("if") or b.startswith("case")):continue
            P.append(c(T,b))
    return P[::2]


LARGE=('tuple','tuple_str','list','list_str','map','casearms','casearms_str','casearms_atom','clauses','clauses_str','condarms','interp','statements','variants','variants_arg','functions','fields','forbody','trybody','typewide','strlen','escapes','heredoc','digits',
       'bindings','bindings_used','letbindings_strings','closures_many','heredoc_holes','ifbody','lambdabody','asserts','scoped_bindings','casestmts','captures','bindings_listed','closures_each','bindings_blocks')
# What one function may hold since statements are compiled in windows of
# the environment (native-scope.alc): 10,000 and 20,000 of each.
HUGE=('bindings','bindings_used','letbindings_strings','closures_many','heredoc_holes','bindings_listed','closures_each','bindings_blocks','statements')


def limits():
    G={}
    def g(name):
        def d(f):G[name]=f;return f
        return d
    J=lambda n,f,sep=", ":sep.join(f(i) for i in range(n))
    def M(defs, body):
        return "defmodule Main do\n"+defs+"  def main() do\n"+"".join("    "+l+"\n" for l in body.split("\n"))+"  end\nend\n"
    @g('tuple')
    def _(n): return M("", "t = {"+J(n,str)+"}\nIO.inspect(elem(t, %d))"%(n-1))
    @g('tuple_inline')
    def _(n): return M("", "IO.inspect({"+J(n,str)+"} == {"+J(n,str)+"})")
    @g('tuple_str')
    def _(n): return M("", "t = {"+J(n,lambda i:'"s%d"'%i)+"}\nIO.puts(elem(t, %d))"%(n-1))
    @g('args')
    def _(n): return M("  def f("+J(n,lambda i:"a%d: integer"%i)+"): integer do\n    a0 + a%d\n  end\n"%(n-1), "IO.inspect(f("+J(n,str)+"))")
    @g('list')
    def _(n): return M("", "IO.inspect(Enum.sum(["+J(n,str)+"]))")
    @g('list_str')
    def _(n): return M("", "l = ["+J(n,lambda i:'"s%d"'%i)+"]\nIO.inspect(length(l))")
    @g('map')
    def _(n): return M("", "m = %{"+J(n,lambda i:"%d => %d"%(i,i))+"}\nIO.inspect(map_size(m))")
    @g('kwlist')
    def _(n): return M("", "m = ["+J(n,lambda i:"k%d: %d"%(i,i))+"]\nIO.inspect(length(m))")
    @g('paren')
    def _(n): return M("", "x = "+"("*n+"1"+")"*n+"\nIO.inspect(x)")
    @g('listnest')
    def _(n): return M("", "x = "+"["*n+"1"+"]"*n+"\nIO.inspect(length(x))")
    @g('tuplenest')
    def _(n): return M("", "x = "+"{"*n+"1"+"}"*n+"\nIO.inspect(x == "+"{"*n+"2"+"}"*n+")")
    @g('callnest')
    def _(n): return M("  def f(a: integer): integer do a + 1 end\n", "x = "+"f("*n+"1"+")"*n+"\nIO.inspect(x)")
    @g('notnest')
    def _(n): return M("", "x = "+"not "*n+"true\nIO.inspect(x)")
    @g('negnest')
    def _(n): return M("", "y = 1\nx = "+"- "*n+"y\nIO.inspect(x)")
    @g('negtight')
    def _(n): return M("", "y = 1\nx = "+"-"*n+"y\nIO.inspect(x)")
    @g('negparen')
    def _(n): return M("", "y = 1\nx = "+"-("*n+"y"+")"*n+"\nIO.inspect(x)")
    @g('ifnest')
    def _(n): return M("", "y = 1\n"+"".join("if y > 0 do\n" for i in range(n))+"IO.puts(\"in\")\n"+"end\n"*n+"IO.puts(\"out\")")
    @g('ifvalnest')
    def _(n): return M("", "y = 1\nx = "+"".join("if y > 0 do " for i in range(n))+"1"+" else 0 end"*n+"\nIO.inspect(x)")
    @g('elsechain')
    def _(n): return M("", "y = %d\nx = "%(n-1)+"".join("if y == %d do %d else "%(i,i) for i in range(n))+"0"+" end"*n+"\nIO.inspect(x)")
    @g('casenest')
    def _(n): return M("", "y = 1\nx = "+"".join("case y do\n  1 -> " for i in range(n))+"7\n"+"  _ -> 0\nend\n"*n+"IO.inspect(x)")
    @g('fnnest')
    def _(n): return None
    @g('interp')
    def _(n): return M("", "a = 1\nIO.inspect(String.length(\""+"#{a}"*n+"\"))")
    @g('strlen')
    def _(n): return M("", "IO.inspect(String.length(\""+"a"*n+"\"))")
    @g('clauses')
    def _(n): return M("".join("  def f(%d) do %d end\n"%(i,i+1) for i in range(n))+"  def f(_) do 0 end\n".replace("def f(_)","def f(x: integer): integer") if False else "  def f(x: integer): integer\n"*0+"".join("  def f(%d): integer do %d end\n"%(i,i+1) if i==0 else "  def f(%d) do %d end\n"%(i,i+1) for i in range(n))+"  def f(_) do 0 end\n", "IO.inspect(f(%d))"%(n-1))
    @g('casearms')
    def _(n): return M("", "y = %d\nx = case y do\n"%(n-1)+"".join("  %d -> %d\n"%(i,i+1) for i in range(n))+"  _ -> 0\nend\nIO.inspect(x)")
    @g('condarms')
    def _(n): return M("", "y = %d\nx = cond do\n"%(n-1)+"".join("  y == %d -> %d\n"%(i,i+1) for i in range(n))+"  true -> 0\nend\nIO.inspect(x)")
    @g('variants')
    def _(n): return M("  type T do\n"+"".join("    v%d\n"%i for i in range(n))+"  end\n", "x = T.v%d\nIO.inspect(x)"%(n-1))
    @g('variants_arg')
    def _(n): return M("  type T do\n"+"".join("    v%d(n: integer)\n"%i for i in range(n))+"  end\n", "x = T.v%d(5)\nIO.inspect(x)"%(n-1))
    @g('fields')
    def _(n): return M("  struct S do\n"+"".join("    f%d: integer\n"%i for i in range(n))+"  end\n", "x = %S{"+J(n,lambda i:"f%d: %d"%(i,i))+"}\nIO.inspect(x.f%d)"%(n-1))
    @g('fields_default')
    def _(n): return M("  struct S do\n"+"".join("    f%d: integer = %d\n"%(i,i) for i in range(n))+"  end\n", "x = %%S{}\nIO.inspect(x.f%d)\ny = %%S{x | f0: 9}\nIO.inspect(y.f0 + y.f%d)"%(n-1,n-1))
    @g('bindings')
    def _(n): return M("", "".join("x%d = %d\n"%(i,i) for i in range(n))+"IO.inspect(x0 + x%d)"%(n-1))
    @g('bindings_used')
    def _(n): return M("", "x0 = 0\n"+"".join("x%d = x%d + 1\n"%(i,i-1) for i in range(1,n))+"IO.inspect(x%d)"%(n-1))
    @g('plus')
    def _(n): return M("", "IO.inspect("+J(n,lambda i:"1"," + ")+")")
    @g('plus_bind')
    def _(n): return M("", "x = "+J(n,lambda i:"1"," + ")+"\nIO.inspect(x)")
    @g('concat')
    def _(n): return M("", "x = "+J(n,lambda i:'"a"'," <> ")+"\nIO.inspect(String.length(x))")
    @g('andchain')
    def _(n): return M("", "y = true\nx = "+J(n,lambda i:"y"," and ")+"\nIO.inspect(x)")
    @g('orchain')
    def _(n): return M("", "y = false\nx = "+J(n,lambda i:"y"," or ")+"\nIO.inspect(x)")
    @g('appendchain')
    def _(n): return M("", "x = "+J(n,lambda i:"[1]"," ++ ")+"\nIO.inspect(length(x))")
    @g('pipechain')
    def _(n): return M("  def f(a: integer): integer do a + 1 end\n", "x = 0"+" |> f()"*n+"\nIO.inspect(x)")
    @g('pipechain_lines')
    def _(n): return M("  def f(a: integer): integer do a + 1 end\n", "x = 0"+"\n  |> f()"*n+"\nIO.inspect(x)")
    @g('indexchain')
    def _(n): return M("", "x = "+"["*n+"1"+"]"*n+"\nIO.inspect(x"+"[0]"*n+")") if n<=200 else M("", "x = [[1]]\nIO.inspect(x"+"[0]"*n+")")
    @g('pattern_tuple')
    def _(n): return M("", "t = {"+J(n,str)+"}\n{"+J(n,lambda i:"a%d"%i)+"} = t\nIO.inspect(a%d)"%(n-1))
    @g('pattern_list')
    def _(n): return M("", "t = ["+J(n,str)+"]\n["+J(n,lambda i:"a%d"%i)+"] = t\nIO.inspect(a%d)"%(n-1))
    @g('pattern_arm')
    def _(n): return M("", "t = ["+J(n,str)+"]\nx = case t do\n  ["+J(n,lambda i:"a%d"%i if i==n-1 else "_")+"] -> a%d\n  _ -> 0\nend\nIO.inspect(x)"%(n-1))
    @g('functions')
    def _(n): return M("".join("  def f%d(a: integer): integer do a + %d end\n"%(i,i) for i in range(n)), "IO.inspect(f%d(1))"%(n-1))
    @g('fnparams')
    def _(n): return M("", "f = fn("+J(n,lambda i:"a%d: integer"%i)+"): integer do a0 + a%d end\nIO.inspect(f.("%(n-1)+J(n,str)+"))")
    @g('lambdaparams')
    def _(n): return M("  def ap(f: fn["+J(n+1,lambda i:"integer")+"]): integer do f.("+J(n,str)+") end\n", "IO.inspect(ap(fn "+J(n,lambda i:"a%d"%i)+" -> a0 + a%d end))"%(n-1))
    @g('captures')
    def _(n): return M("", "".join("x%d = %d\n"%(i,i) for i in range(n))+"f = fn(a: integer): integer do a + x%d end\nIO.inspect(f.(1))"%(n-1))
    @g('forgens')
    def _(n): return M("", "x = for "+J(n,lambda i:"a%d <- [1]"%i)+" do a0 + a%d end\nIO.inspect(x)"%(n-1))
    @g('withclauses')
    def _(n): return M("", "x = with "+J(n,lambda i:"ok(a%d) <- ok(%d)"%(i,i))+" do a%d else error(_) -> 0 - 1 end\nIO.inspect(x)"%(n-1)) if False else M("  def r(i: integer): result[integer, string] do ok(i) end\n", "x = with "+J(n,lambda i:"ok(a%d) <- r(%d)"%(i,i))+" do\n  a%d\nelse\n  error(_) -> 0 - 1\nend\nIO.inspect(x)"%(n-1))
    @g('ident')
    def _(n): return M("", "a"*n+" = 1\nIO.inspect("+"a"*n+")")
    @g('atomlen')
    def _(n): return M("", "x = :"+"a"*n+"\nIO.inspect(String.length(to_string(x)))")
    @g('atoms')
    def _(n): return M("", "x = ["+J(n,lambda i:":a%d"%i)+"]\nIO.inspect(length(x))")
    @g('digits')
    def _(n): return M("", "x = "+"0"*n+"7\nIO.inspect(x)")
    @g('guard')
    def _(n): return M("  def f(x: integer): integer when "+J(n,lambda i:"x == %d"%i," or ")+" do 1 end\n  def f(_) do 0 end\n", "IO.inspect(f(%d))"%(n-1))
    @g('heredoc')
    def _(n): return M("", "x = \"\"\"\n"+"line\n"*n+"\"\"\"\nIO.inspect(String.length(x))")
    @g('escapes')
    def _(n): return M("", "IO.inspect(String.length(\""+"\\n"*n+"\"))")
    @g('typenest')
    def _(n): return M("  def f(x: "+"list["*n+"integer"+"]"*n+"): integer do 1 end\n", "IO.inspect(f("+"["*n+"]"*n+"))")
    @g('typewide')
    def _(n): return M("  def f(x: tuple["+J(n,lambda i:"integer")+"]): integer do elem(x, %d) end\n"%(n-1), "IO.inspect(f({"+J(n,str)+"}))")
    @g('defaults')
    def _(n): return M("  def f("+J(n,lambda i:"a%d: integer \\\\ %d"%(i,i))+"): integer do a0 + a%d end\n"%(n-1), "IO.inspect(f())\nIO.inspect(f(5))")
    @g('statements')
    def _(n): return M("", "IO.puts(\"a\")\n"*n)
    @g('modules')
    def _(n): return None
    @g('structs')
    def _(n): return M("".join("  struct S%d do\n    a: integer\n  end\n"%i for i in range(n)), "x = %%S%d{a: 3}\nIO.inspect(x.a)"%(n-1))
    @g('fieldchain')
    def _(n): return M("  struct S do\n    a: option[S]\n    v: integer\n  end\n", "x = %S{a: none, v: 1}\nIO.inspect(x.v)") if False else None
    @g('mapnest')
    def _(n): return M("", "x = "+"%{1 => "*n+"1"+"}"*n+"\nIO.inspect(map_size(x))")
    @g('somenest')
    def _(n): return M("", "x = "+"some("*n+"1"+")"*n+"\nIO.inspect(x != none)")
    @g('listlines')
    def _(n): return M("", "x = [\n"+"".join("  %d,\n"%i for i in range(n-1))+"  0\n]\nIO.inspect(length(x))")
    @g('strlist_inline')
    def _(n): return M("", "IO.inspect(length(["+J(n,lambda i:'"s%d"'%i)+"]))")
    @g('callargs_exprs')
    def _(n): return M("  def f(a: list[integer], b: integer): integer do length(a) + b end\n", "IO.inspect(f(["+J(n,lambda i:"%d + 1"%i)+"], 1))")

    @g('lamnest')
    def _(n): return M("", "f: "+"fn[integer, "*n+"integer"+"]"*n+" = "+"".join("fn a%d -> "%i for i in range(n))+"a0"+" end"*n+"\nIO.inspect(f"+".(1)"*n+")")
    @g('strcat_lines')
    def _(n): return M("", "x = \"a\" <>\n"+"".join("  \"b\" <>\n" for i in range(n))+"  \"c\"\nIO.inspect(String.length(x))")
    @g('nestedcalls_args')
    def _(n): return M("  def f(a: integer, b: integer): integer do a + b end\n", "x = "+"f(1, "*n+"1"+")"*n+"\nIO.inspect(x)")
    @g('maplines')
    def _(n): return M("", "m = %{\n"+"".join("  \"k%d\" => %d,\n"%(i,i) for i in range(n-1))+"  \"z\" => 0\n}\nIO.inspect(map_size(m))")
    @g('listoflists')
    def _(n): return M("", "m = ["+J(n,lambda i:"[%d, %d]"%(i,i))+"]\nIO.inspect(length(m))")
    @g('listoftuples')
    def _(n): return M("", "m = ["+J(n,lambda i:"{%d, \"s%d\"}"%(i,i))+"]\nIO.inspect(length(m))")
    @g('structlist')
    def _(n): return M("  struct P do\n    x: integer\n    y: integer\n  end\n", "m = ["+J(n,lambda i:"%%P{x: %d, y: %d}"%(i,i))+"]\nIO.inspect(length(m))")
    @g('whenchain')
    def _(n): return M("", "y = %d\nx = case y do\n  k when "%(n-1)+J(n,lambda i:"k == %d"%i," or ")+" -> 1\n  _ -> 0\nend\nIO.inspect(x)")
    @g('inlist')
    def _(n): return M("", "y = %d\nIO.inspect(y in ["%(n-1)+J(n,str)+"])")
    @g('asserts')
    def _(n): return M("", "".join("x%d = %d\nassert(x%d == %d)\n"%(i,i,i,i) for i in range(n))+"IO.puts(\"ok\")")
    @g('scoped_bindings')
    def _(n): return M("", "".join("if true do\n  x%d = %d\n  IO.inspect(x%d)\nend\n"%(i,i,i) for i in range(n))+"IO.puts(\"ok\")")
    @g('casestmts')
    def _(n): return M("", "y = some(1)\n"+"".join("case y do\n  some(v%d) -> IO.inspect(v%d)\n  none -> IO.puts(\"n\")\nend\n"%(i,i) for i in range(n))+"IO.puts(\"ok\")")

    @g('typeparams')
    def _(n): return M("  struct S["+J(n,lambda i:"t%d"%i)+"] do\n"+"".join("    f%d: t%d\n"%(i,i) for i in range(n))+"  end\n", "x = %S{"+J(n,lambda i:"f%d: %d"%(i,i))+"}\nIO.inspect(x.f%d)"%(n-1))
    @g('genericvars')
    def _(n): return M("  def f("+J(n,lambda i:"a%d: t%d"%(i,i))+"): t%d do a%d end\n"%(n-1,n-1), "IO.inspect(f("+J(n,str)+"))")
    @g('forbody')
    def _(n): return M("", "r = for i <- [1, 2] do\n"+"  IO.puts(\"a\")\n"*n+"  i\nend\nIO.inspect(r)")
    @g('trybody')
    def _(n): return M("", "try do\n"+"  IO.puts(\"b\")\n"*n+"rescue\n  _ -> IO.puts(\"no\")\nend")
    @g('ifbody')
    def _(n): return M("", "y = 1\nif y > 0 do\n"+"".join("  z%d = %d\n"%(i,i) for i in range(n))+"  IO.inspect(z0 + z%d)\nend"%(n-1))
    @g('lambdabody')
    def _(n): return M("", "f = fn(a: integer): integer do\n"+"".join("  z%d = a + %d\n"%(i,i) for i in range(n))+"  z0 + z%d\nend\nIO.inspect(f.(1))"%(n-1))
    @g('closures_many')
    def _(n): return M("", "k = 5\n"+"".join("f%d = fn(a: integer): integer do a + k + %d end\n"%(i,i) for i in range(n))+"IO.inspect(f0.(1) + f%d.(1))"%(n-1))
    @g('casearms_str')
    def _(n): return M("", "y = \"s%d\"\nx = case y do\n"%(n-1)+"".join("  \"s%d\" -> %d\n"%(i,i+1) for i in range(n))+"  _ -> 0\nend\nIO.inspect(x)")
    @g('casearms_atom')
    def _(n): return M("", "y = :a%d\nx = case y do\n"%(n-1)+"".join("  :a%d -> %d\n"%(i,i+1) for i in range(n))+"  _ -> 0\nend\nIO.inspect(x)")
    @g('casearms_variant')
    def _(n): return M("  type T do\n"+"".join("    v%d\n"%i for i in range(n))+"  end\n", "y = T.v%d\nx = case y do\n"%(n-1)+"".join("  T.v%d -> %d\n"%(i,i+1) for i in range(n))+"end\nIO.inspect(x)")
    @g('casearms_fields')
    def _(n): return M("  type T do\n"+"".join("    v%d(n: integer)\n"%i for i in range(n))+"  end\n", "y = T.v%d(7)\nx = case y do\n"%(n-1)+"".join("  T.v%d(k) -> k + %d\n"%(i,i) for i in range(n))+"end\nIO.inspect(x)")
    @g('casearms_guard')
    def _(n): return M("", "y = %d\nx = case y do\n"%(n-1)+"".join("  k when k == %d -> %d\n"%(i,i+1) for i in range(n))+"  _ -> 0\nend\nIO.inspect(x)")
    @g('casearms_twice')
    def _(n): return M("", "y = 1\nx = case y do\n"+"".join("  %d -> %d\n"%(i,i+1) for i in range(n))+"  %d -> 0\n  _ -> 0\nend\nIO.inspect(x)"%(n//2))
    @g('casearms_open')
    def _(n): return M("", "y = 1\nx = case y do\n"+"".join("  %d -> %d\n"%(i,i+1) for i in range(n))+"end\nIO.inspect(x)")
    @g('casearms_after')
    def _(n): return M("", "y = 1\nx = case y do\n  _ -> 0\n"+"".join("  %d -> %d\n"%(i,i+1) for i in range(n))+"end\nIO.inspect(x)")
    @g('clauses_two')
    def _(n): return M("  def f(0, b: integer): integer do b end\n"+"".join("  def f(%d, b) do b + %d end\n"%(i,i) for i in range(1,n))+"  def f(_, _) do 0 end\n", "IO.inspect(f(%d, 1))"%(n-1))
    @g('clauses_twice')
    def _(n): return M("  def f(0): integer do 1 end\n"+"".join("  def f(%d) do %d end\n"%(i,i+1) for i in range(1,n))+"  def f(%d) do 0 end\n  def f(_) do 0 end\n"%(n//2), "IO.inspect(f(1))")
    @g('clauses_str')
    def _(n): return M("  def f(\"s0\"): integer do 1 end\n"+"".join("  def f(\"s%d\") do %d end\n"%(i,i+1) for i in range(1,n))+"  def f(_) do 0 end\n", "IO.inspect(f(\"s%d\"))"%(n-1))
    @g('interp_exprs')
    def _(n): return M("", "a = 1\nIO.inspect(String.length(\""+"".join("x#{a + %d}"%i for i in range(n))+"\"))")
    @g('heredoc_holes')
    def _(n): return M("", "a = 1\nx = \"\"\"\n"+"line #{a}\n"*n+"\"\"\"\nIO.inspect(String.length(x))")
    @g('floatdigits')
    def _(n): return M("", "x = 1."+"0"*n+"5\nIO.inspect(x)")
    @g('hexdigits')
    def _(n): return M("", "x = 0x"+"0"*n+"ff\nIO.inspect(x)")
    @g('bigint')
    def _(n): return M("", "x = "+"9"*n+"\nIO.inspect(x)")
    @g('structupdate')
    def _(n): return M("  struct S do\n"+"".join("    f%d: integer\n"%i for i in range(n))+"  end\n", "x = %S{"+J(n,lambda i:"f%d: %d"%(i,i))+"}\ny = %S{x | "+J(n,lambda i:"f%d: %d"%(i,i+1))+"}\nIO.inspect(y.f%d)\nIO.inspect(x == y)"%(n-1))
    @g('structinspect')
    def _(n): return M("  struct S do\n"+"".join("    f%d: integer\n"%i for i in range(n))+"  end\n", "x = %S{"+J(n,lambda i:"f%d: %d"%(i,i))+"}\nIO.inspect(String.length(inspect(x)))")
    @g('tupleinspect')
    def _(n): return M("", "t = {"+J(n,str)+"}\nIO.inspect(String.length(inspect(t)))")
    @g('variantsinspect')
    def _(n): return M("  type T do\n"+"".join("    v%d(n: integer)\n"%i for i in range(n))+"  end\n", "l = [T.v0(1), T.v%d(2)]\nIO.inspect(l)\nIO.inspect(hd(l) == T.v0(1))"%(n-1))
    @g('lambdaargs')
    def _(n): return M("  def ap(f: fn[integer, integer], "+J(n,lambda i:"a%d: integer"%i)+"): integer do f.(a%d) end\n"%(n-1), "IO.inspect(ap(fn x -> x + 1 end, "+J(n,str)+"))")
    @g('pipeargs')
    def _(n): return M("  def f("+J(n,lambda i:"a%d: integer"%i)+"): integer do a0 + a%d end\n"%(n-1), "IO.inspect(5 |> f("+J(n-1,str)+"))") if n>1 else None
    @g('maplit_str')
    def _(n): return M("", "m = %{"+J(n,lambda i:"\"k%d\" => \"v%d\""%(i,i))+"}\nIO.inspect(map_size(m))")
    @g('nestedtuples')
    def _(n): return M("", "t = {"+J(n,lambda i:"{%d, \"s\"}"%i)+"}\nIO.inspect(elem(elem(t, %d), 0))"%(n-1))
    @g('listpattern_cons')
    def _(n): return M("", "t = ["+J(n+1,str)+"]\n["+J(n,lambda i:"a%d"%i)+" | rest] = t\nIO.inspect(a%d + length(rest))"%(n-1))
    @g('letbindings_strings')
    def _(n): return M("", "".join("x%d = \"v%d\"\n"%(i,i) for i in range(n))+"IO.puts(x0 <> x%d)"%(n-1))
    @g('withelse')
    def _(n): return M("  def r(i: integer): result[integer, string] do if i > 0 do ok(i) else error(\"e\") end end\n", "x = with ok(a) <- r(0) do\n  a\nelse\n"+"".join("  error(\"x%d\") -> %d\n"%(i,i) for i in range(n))+"  error(_) -> 0 - 1\nend\nIO.inspect(x)")

    @g('bindings_listed')
    def _(n): return M("", "".join("x%d = %d\n"%(i,i) for i in range(n))+"l = ["+J(n,lambda i:"x%d"%i)+"]\nIO.inspect(length(l) + x%d)"%(n-1))
    @g('closures_each')
    def _(n): return M("", "".join("x%d = %d\nf%d = fn(a: integer): integer do a + x%d end\n"%(i,i,i,i) for i in range(n))+"IO.inspect(f0.(1) + f%d.(1))"%(n-1))
    @g('bindings_blocks')
    def _(n): return M("", "".join("x%d = %d\nif x%d > 0 do\n  y%d = x%d + 1\n  IO.inspect(y%d)\nend\n"%(i,i,i,i,i,i) if i%100==0 else "x%d = %d\n"%(i,i) for i in range(n))+"IO.inspect(x0 + x%d)"%(n-1))

    P=[]
    for name,f in G.items():
        for n in [30,64,126,127,129,201,250,251,253,257,300,1000,1024,1026,2000,5000,10000,20000]:
            # 5,000 only of what the gate can run eight at a time.
            if n==5000 and name not in LARGE:continue
            if n>5000 and name not in HUGE:continue
            try:s=f(n)
            except (TypeError,ValueError):s=None
            if s is not None and len(s)<(60000 if n<=1026 else 200000 if n<=5000 else 1000000):P.append(s)
    return P


def upstream(source):
    with tempfile.TemporaryDirectory() as d:
        path=Path(d)/'p.alc';path.write_text(source)
        try:run=subprocess.run([str(UPSTREAM),'run',str(path)],capture_output=True,env=ENV,cwd=d,stdin=subprocess.DEVNULL,timeout=150)
        except subprocess.TimeoutExpired:return ['timeout','','']
        out=run.stdout.decode('utf8','replace');err=run.stderr.decode('utf8','replace').replace(str(path),'<stdin>')
        # A compile error: nothing printed, status 1 and a diagnostic at a position of the file.
        if run.returncode==1 and not out and err.startswith('<stdin>:') and '\n  at ' not in err:return [None,'',err]
        # The pinned compiler's own Go build ran out of its memory or time ceiling: no answer.
        if run.returncode in (-9,137) or 'go build: context canceled' in err or 'signal: killed' in err:return ['resources','','']
        return [run.returncode,out,err]


def native(source):
    with tempfile.TemporaryDirectory() as d:
        built=subprocess.run([str(ROOT/'scripts/limited'),str(NATIVE)],input=source.encode(),capture_output=True,env=dict(os.environ,ALCHEM_MEMORY='1G',ALCHEM_SECONDS='60'))
        if built.returncode==65 and not built.stdout:return [None,'','']
        if built.returncode:return ['compiler %d'%built.returncode,'','']
        out=Path(d)/'p';out.write_bytes(built.stdout);out.chmod(0o700)
        for attempt in range(50):
            # Another thread's fork may still hold the file open for writing.
            try:run=subprocess.run([str(out)],capture_output=True,env={'PATH':''},cwd=d,stdin=subprocess.DEVNULL,timeout=60);break
            except subprocess.TimeoutExpired:return ['timeout','','']
            except OSError as error:
                if error.errno!=26 or attempt==49:raise
        return [run.returncode,run.stdout.decode('utf8','replace'),run.stderr.decode('utf8','replace')]


def main():
    hand=json.loads(lzma.decompress((ROOT/'harness/gaps-hand.json.xz').read_bytes()))
    programs=list(dict.fromkeys(hand+lambdas()+bodies()+limits()))
    kept_path=ROOT/'build/dev/gaps-upstream.json'
    kept=json.loads(kept_path.read_text()) if kept_path.exists() else {}
    key=lambda s:hashlib.sha1(s.encode()).hexdigest()
    todo=[s for s in programs if key(s) not in kept]
    with ThreadPoolExecutor(4) as pool:
        for s,r in zip(todo,pool.map(upstream,todo)):kept[key(s)]=r
    kept_path.write_text(json.dumps(kept))
    with ThreadPoolExecutor(4) as pool:ours=list(pool.map(native,programs))
    cases=[];differ=[]
    unanswered=0
    for s,n in zip(programs,ours):
        u=kept[key(s)]
        # No answer from the pinned compiler (its Go build exceeded the ceiling of the wrapper): nothing to hold a case to.
        if u[0] in ('timeout','resources') or (u[0]==1 and 'go build: context canceled' in u[2]) or u[0]==-9:unanswered+=1;continue
        same=(u[0] is None and n[0] is None) or (u[0] is not None and u==n)
        if same:cases.append([s,u[0],u[1],u[2] if u[0] is not None else ''])
        else:differ.append((s,u,n))
    (ROOT/'harness/gaps-cases.json.xz').write_bytes(lzma.compress(json.dumps(cases).encode(),preset=9))
    for s,u,n in differ:print('DIFFERS',repr(s[:300]),'| pinned',u[0],repr(u[1][-80:]),repr(u[2][-160:]),'| native',n[0],repr(n[1][-80:]),repr(n[2][-80:]))
    print(len(cases),'cases written,',sum(1 for c in cases if c[1] is None),'of them rejections;',len(differ),'programs differ and are left out;',unanswered,'had no answer from the pinned compiler within its ceiling')


if __name__=='__main__':main()
