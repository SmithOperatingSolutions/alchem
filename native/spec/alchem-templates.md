# HTML templates and Markup

`~h"..."`, `~h"""..."""` and `~H` follow the pinned compiler, and so does
the `Markup` module. `harness/templates.py` holds 16 programs with the
pinned compiler's output and 8 it rejects; the library reference's seven
`Markup` examples and the syntax reference's template example pass. The
code is `implementations/alchem/native-templates.alc` and
`library/Markup.alc`.

## The sigil

A template is rewritten before the program is compiled
(`alchem-macros.md`), as the pinned checker rewrites it:

```alchem
~h"<li>#{name}</li>"   ->   Markup.template(NAME, ["<li>", "</li>"], [Markup.of(name)])
```

- The fixed pieces are the template's own text around its values, one more
  than there are values, written as string literals: the text has no
  escapes but a backslash before the closing delimiter, and a heredoc's
  lines lose the closing line's indentation (`sg_kept`, the rule of every
  sigil). Every delimiter a sigil may have is taken.
- The name is the FNV-1a sum (64 bits) of the fixed pieces, each followed
  by a zero byte, in sixteen hexadecimal digits: the same for every value
  of one `~h` and for another only with the same text.
- A value is `Markup.of(code)`. `#{` holds a value even after a backslash,
  as in every sigil that holds values. `~H` holds none: its text is one
  fixed piece.
- A modifier after the sigil is rejected, and so is a value `Markup.of` has
  no form for (a boolean, a map, an option).

The code of a value stands, for the pinned compiler, on the sigil's line at
a column counted in the string its parser makes of the template (the tilde's
column, the characters of that string up to the `#{`, the code's own
offset): two columns left of where it is written in a one-line template,
and on the opening line for a heredoc. Failures are named there: a moved
record anchors the code at the sigil (`alchem-traces.md`).

## Markup

`library/Markup.alc` declares

```alchem
struct Markup do html: string ... end
type Markup.Value do text(text: string) markup(markup: Markup) list(items: list[Markup]) end
struct Markup.Parts do template: string  fixed: list[string]  values: list[Markup.Value] end
```

and `raw`, `escape`, `to_string`, `join`, `template`, `parts` and the six
forms of `of`. The pinned runtime keeps beside a Markup's text how it was
made, which `inspect` and `==` do not see. Here that is a second field of
the struct: 0 from text, 1 by a template with its name, pieces and values,
2 by joining its values. Its name ends in byte 127, which no program can
write, and a field so named is no part of its struct's value: `inspect`
and `==` pass over it and the fields after it (`ni_shown`). A program may
still write `%Markup{html: text}`; the field has a default.

The field is seen nowhere else either. Equality made for a type that
holds a Markup (a tuple, a list, an option, `in`, `Enum.uniq`,
`Enum.dedup`, `List.delete`) goes through the struct's own equality. A
Markup has no order and is no key, in the pinned compiler as here:
`Enum.sort`, `Enum.max`, `<`, a map key, `MapSet.new`, `Enum.group_by` and
`Enum.frequencies` over Markup are rejected by both, so the compiler-made
ordering (`native-ordering.alc`) and the key routines never meet the field.

`Markup.Value.text(...)` names a sum type of the library by its dotted
name, in constructors and patterns (`nv_typed`: a struct called `Markup`
does not stand in its way), and two declarations of the library may share a
first name: a dotted name is looked for whole when the table is checked
(`nc_record_valid`).

## Differences from the pinned compiler that remain

- The code of a value ends on its line, as in every sigil
  (`alchem-sigils.md`): the pinned compiler takes a value written across
  the lines of a heredoc template.
- The column of a failure in a value's code counts bytes within that code
  and the pieces before it as the pinned parser counts characters; a
  character of several bytes in the value's own code before the failing
  place moves the column by its extra bytes.
- A fixed piece holds at most 65535 bytes, as a string literal does.
- Inside a function that `use` adds, a failure in a template's value is
  shown in the template's own file, not the using module's.
- `Markup.escape` and the forms of `of` build their text by the library's
  `String.replace`; a failure cannot arise in them.
- Every compile error is `E_COMPILE`.
