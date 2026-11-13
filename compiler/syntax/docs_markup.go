package syntax

func init() {
	module("Markup", "Text", "HTML built by ~h templates, which escape every value they interpolate; see alchem syntax templates.")

	doc("Markup.raw", "Markup made from text exactly as given, for HTML the program trusts: never for text from users.",
		"alx> Markup.to_string(Markup.raw(\"<br>\"))", "\"<br>\"")
	doc("Markup.escape", "Text made safe inside an HTML element or a quoted attribute value: &, <, >, \" and ' become character references.",
		"alx> Markup.escape(\"<a href='x'>&</a>\")", "\"&lt;a href=&#39;x&#39;&gt;&amp;&lt;/a&gt;\"")
	doc("Markup.to_string", "The HTML text of markup, to send or store.",
		"alx> name = \"<b>ada</b>\"", "alx> Markup.to_string(~h\"<p>#{name}</p>\")", "\"<p>&lt;b&gt;ada&lt;/b&gt;</p>\"")
	doc("Markup.join", "Pieces of markup one after another.",
		"alx> items = Enum.map([\"a\", \"b\"], fn x -> ~h\"<li>#{x}</li>\" end)", "alx> Markup.to_string(Markup.join(items))", "\"<li>a</li><li>b</li>\"")
	doc("Markup.parts", "Takes markup apart, for a library that sends a page's fixed text once and afterwards only what changed. For markup a ~h template made: template names the template (the same for every value of one ~h, and for another only when its text is the same), fixed is the template's own text in the pieces around its values (one more piece than there are values), and values are the values in order: text already escaped, the Markup of a template inside it, or the list of Markup a list gave. Markup made by Markup.raw, Markup.of or Markup.join has nothing fixed: an empty name, two empty pieces and one value, its text or its list.",
		"alx> name = \"<ada>\"", "alx> parts = Markup.parts(~h\"<p>#{name}</p>\")", "alx> {parts.fixed, parts.values}", "{[\"<p>\", \"</p>\"], [Markup.Value.text(\"&lt;ada&gt;\")]}",
		"alx> parts.template == Markup.parts(~h\"<p>#{name}</p>\").template", "true",
		"alx> Markup.parts(Markup.raw(\"<br>\")).values", "[Markup.Value.text(\"<br>\")]")
	doc("Markup.template", "What ~h builds: markup from a template's name, its fixed text in pieces and the values that go between them. Written by the compiler; a program writes ~h.",
		"alx> Markup.to_string(Markup.template(\"greeting\", [\"<p>\", \"</p>\"], [Markup.of(\"hi\")]))", "\"<p>hi</p>\"")
	doc("Markup.of", "What a template does with a value it is given: a string is escaped, markup is kept, a number or atom is written as text and a list of markup is joined.",
		"alx> Markup.to_string(Markup.of(\"1 < 2\"))", "\"1 &lt; 2\"",
		"alx> Markup.to_string(Markup.of(~h\"<i>kept</i>\"))", "\"<i>kept</i>\"",
		"alx> Markup.to_string(Markup.of(42))", "\"42\"")
}
