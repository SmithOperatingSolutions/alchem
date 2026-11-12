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
	doc("Markup.of", "What a template does with a value it is given: a string is escaped, markup is kept, a number or atom is written as text and a list of markup is joined.",
		"alx> Markup.to_string(Markup.of(\"1 < 2\"))", "\"1 &lt; 2\"",
		"alx> Markup.to_string(Markup.of(~h\"<i>kept</i>\"))", "\"<i>kept</i>\"",
		"alx> Markup.to_string(Markup.of(42))", "\"42\"")
}
