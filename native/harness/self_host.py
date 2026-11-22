#!/usr/bin/env python3
"""A1/A2/A3 rebuild the actual assembled Alchem compiler, then run its suites."""
from concurrent.futures import ThreadPoolExecutor
import os
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
from run import ROOT
from native_memory import profile,TraceUnavailable
from alchem_compiler import verify as verify_integers
from alchem_byte_compiler import verify as verify_bytes
from enum_library import verify as verify_enum
from string_library import verify as verify_strings
from boolean_library import verify as verify_booleans
from options import verify as verify_options
from graphemes import verify as verify_graphemes
from source_capacity import verify as verify_capacity
from general_collections import verify as verify_collections
from maps import verify as verify_maps
from collection_memory import verify as verify_collection_memory
from library_expansion import verify as verify_library_expansion
from integer_parse import verify as verify_integer_parse
from io_input import verify as verify_io_input
from system_env import verify as verify_system_env
from effect_helpers import verify as verify_effect_helpers
from file_read import verify as verify_file_read
from string_ops import verify as verify_string_ops
from string_case import verify as verify_string_case
from string_graphemes import verify as verify_string_graphemes
from modules import verify as verify_modules
from closures import verify as verify_closures
from pipes import verify as verify_pipes
from records import verify as verify_records
from equality import verify as verify_equality
from patterns import verify as verify_patterns
from generics import verify as verify_generics
from inference import verify as verify_inference
from long_bodies import verify as verify_long_bodies
from statements import verify as verify_statements
from traces import verify as verify_traces
from packages import verify as verify_packages
from literals import verify as verify_literals
from wide import verify as verify_wide
from operators import verify as verify_operators
from inspection import verify as verify_inspection
from library import verify as verify_library
from forms import verify as verify_forms
from atoms import verify as verify_atoms
from speed import verify as verify_speed
from failures import verify as verify_failures
from memory_reclaim import verify as verify_memory_reclaim
from tail_calls import verify as verify_tail_calls
from lists import verify as verify_lists
from ordering import verify as verify_ordering
from processes import verify as verify_processes
from macros import verify as verify_macros
from protocols import verify as verify_protocols
from templates import verify as verify_templates
from parsing import verify as verify_parsing
from network import verify as verify_network
from diskstore import verify as verify_diskstore
from sets import verify as verify_sets
from streams import verify as verify_streams
from exceptions import verify as verify_exceptions
from system import verify as verify_system
from ranges import verify as verify_ranges
from sigils import verify as verify_sigils
from regex import verify as verify_regex
from crypto import verify as verify_crypto
from nodes import verify as verify_nodes
from tls import verify as verify_tls
from gaps import verify as verify_gaps
from described import verify as verify_described
from nil_forms import verify as verify_nil_forms
from test_driver import verify as verify_test_driver
from commands import verify as verify_commands
from json_library import verify as verify_json_library
from time_zones import verify as verify_time_zones
from logger import verify as verify_logger
from gen import verify as verify_gen
from testing import verify as verify_testing
from clauses import verify as verify_clauses
from comprehensions import verify as verify_comprehensions
from floats import verify as verify_floats
from structural_types import verify as verify_structural
from type_words import verify as verify_type_words


def source():
    spec=importlib.util.spec_from_file_location('bootstrap',ROOT/'scripts/bootstrap-alchem-compiler.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module.source_text('functions').encode()


def verify(frontend,backends):
    text=source();records=[]
    with tempfile.TemporaryDirectory(prefix='alchem-self-host-') as directory:
        root=Path(directory);stages=[];seed_images=[]
        for index,backend in enumerate(backends):
            seed=root/f'A0-{index}'
            built=subprocess.run([sys.executable,str(ROOT/'scripts/bootstrap-alchem-compiler.py'),'--language','functions','--frontend',str(frontend),'--backend',str(backend),'--output',str(seed)],capture_output=True,timeout=120)
            assert built.returncode==0,built.stderr
            seed_images.append(seed.read_bytes());previous=seed
            for stage in range(1,4):
                image=root/f'A{stage}-{index}'
                result=subprocess.run([str(previous)],input=text,capture_output=True,env={'PATH':''},timeout=120)
                assert result.returncode==0 and not result.stderr,('self rebuild',index,stage,result.returncode,result.stderr)
                image.unlink(missing_ok=True);image.write_bytes(result.stdout);image.chmod(0o700)
                if index==0:stages.append(image)
                else:assert image.read_bytes()==stages[stage-1].read_bytes(),('backend self rebuild differs',stage)
                try:
                    status,data,errors,charged=profile(previous,text,1<<34)
                    assert (status,data,errors)==(0,result.stdout,b''),('traced rebuild',stage,status,errors)
                    assert 0<charged<=(1<<34),('charged arena',stage,charged)
                    records.append({'backend':index,'build':stage,'charged_bytes':charged})
                except TraceUnavailable:print('SKIP self-build arena measurement: ptrace unavailable')
                previous=image
        assert seed_images[0]==seed_images[1],'bootstrap artifacts differ'
        assert stages[0].read_bytes()==stages[1].read_bytes()==stages[2].read_bytes(),'A1/A2/A3 mismatch'
        # A1, A2 and A3 were just shown to be the same bytes, so the gates run
        # once, on A3, and side by side: each compiles and runs its own programs.
        compiler=stages[2]
        gates=[verify_integers,verify_bytes,verify_enum,verify_strings,verify_booleans,verify_options,verify_structural,verify_collections,verify_maps,verify_library_expansion,verify_integer_parse,verify_io_input,verify_system_env,verify_effect_helpers,verify_file_read,verify_string_ops,verify_string_case,verify_string_graphemes,verify_modules,verify_closures,verify_pipes,verify_records,verify_equality,verify_patterns,verify_generics,verify_inference,verify_long_bodies,verify_statements,verify_traces,verify_packages,verify_literals,verify_wide,verify_operators,verify_inspection,verify_library,verify_forms,verify_atoms,verify_failures,verify_tail_calls,verify_lists,verify_ordering,verify_sets,verify_streams,verify_exceptions,verify_ranges,verify_system,verify_sigils,verify_regex,verify_crypto,verify_nodes,verify_tls,verify_json_library,verify_time_zones,verify_logger,verify_gen,verify_testing,verify_macros,verify_protocols,verify_templates,verify_parsing,verify_clauses,verify_comprehensions,verify_floats,verify_collection_memory,verify_type_words,verify_capacity,verify_graphemes,verify_processes,verify_network,verify_diskstore,verify_gaps,verify_memory_reclaim,verify_described,verify_speed,verify_nil_forms,verify_test_driver,verify_commands]
        # Each gate is a process of its own: threads that write and start
        # executables in one process trip over each other's open files.
        def run(gate):
            # The two oldest gates compare compilers: they get A2 and A3.
            call='m.verify(Path(%r),[Path(%r)]*2,[Path(%r),Path(%r)])'%(str(frontend),str(backends[0]),str(stages[1]),str(stages[2])) if gate in (verify_integers,verify_bytes) else f'm.verify(Path({str(compiler)!r}))'
            code=f'import sys;from pathlib import Path;sys.path.insert(0,{str(ROOT/"harness")!r});import {gate.__module__} as m;'+call
            return gate.__module__,subprocess.run([sys.executable,'-c',code],capture_output=True,cwd=ROOT/'harness')
        with ThreadPoolExecutor(max_workers=os.cpu_count() or 4) as pool:
            for name,done in pool.map(run,gates):
                sys.stdout.write(done.stdout.decode(errors='replace'))
                assert done.returncode==0,(name,done.stderr.decode(errors='replace')[-2000:])
        published=root/'published'
        built=subprocess.run([sys.executable,str(ROOT/'scripts/build-self-hosted.py'),'--frontend',str(frontend),'--backend',str(backends[0]),'--output-directory',str(published)],capture_output=True,timeout=120)
        assert built.returncode==0,built.stderr
        assert (published/'alchem-compiler').read_bytes()==stages[2].read_bytes()
        assert (published/'compiler-source.alc').read_bytes()==text
        manifest=json.loads((published/'self-host.json').read_text())
        assert len(set(manifest['stage_sha256']))==1 and manifest['compiler_sha256']==hashlib.sha256(stages[2].read_bytes()).hexdigest()
        before={p.name:p.read_bytes() for p in published.iterdir()}
        failed=subprocess.run([sys.executable,str(ROOT/'scripts/build-self-hosted.py'),'--frontend',str(frontend),'--backend','/bin/false','--output-directory',str(published)],capture_output=True,timeout=120)
        assert failed.returncode!=0 and before=={p.name:p.read_bytes() for p in published.iterdir()},'failed build replaced published artifacts'
        result={'source_bytes' :len(text),'source_sha256':hashlib.sha256(text).hexdigest(),'compiler_bytes':stages[2].stat().st_size,'compiler_sha256':hashlib.sha256(stages[2].read_bytes()).hexdigest(),'arena_measurements':records}
        print('SELF_HOST_RESULT '+json.dumps(result,sort_keys=True))
    print('PASS self-hosting: actual source -> A1 -> A2 -> A3, identical bytes, empty PATH; every gate on A3')


if __name__=='__main__':verify(Path(sys.argv[1]).resolve(),[Path(p).resolve() for p in sys.argv[2:]])
