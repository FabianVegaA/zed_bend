; Syntax highlighting for Bend (v2 grammar).
; Specific patterns first, generic fallbacks last.

(comment) @comment

; ---------------- definitions ----------------

(function_definition
  name: (identifier) @function)

(function_definition
  name: (dotted_name
    (identifier) @function))

(type_definition
  name: (identifier) @type)

(type_constructor
  name: (identifier) @constructor)

(law_definition
  name: (identifier) @function)

(import_statement
  "import" @keyword)

(import_statement
  alias: (identifier) @variable)

; ---------------- parameters, fields, binds ----------------

(parameter
  name: (identifier) @variable.parameter)

(type_parameter
  name: (identifier) @type)

(constructor_field
  name: (identifier) @property)

(do_bind
  name: (identifier) @variable)

(do_let
  name: (identifier) @variable)

; ---------------- types in annotation positions ----------------

(parameter
  type: (identifier) @type)

(constructor_field
  type: (identifier) @type)

(type_parameter
  type: (identifier) @type)

(function_definition
  return_type: (identifier) @type)

(generic_type
  type: (identifier) @type)

(generic_type
  (identifier) @type)

(call_type
  function: (identifier) @type)

; ---------------- terms ----------------

(constructor_pattern
  name: (identifier) @constructor)

(constructor_pattern
  name: (attribute_expression
    attribute: (identifier) @constructor))

(constructor_expression
  name: (identifier) @constructor)

(constructor_expression
  name: (attribute_expression
    attribute: (identifier) @constructor))

(call_expression
  function: (identifier) @function.call)

(call_expression
  function: (attribute_expression
    attribute: (identifier) @function.call))

(gpu_call_expression
  function: (identifier) @function.call)

(gpu_call_expression
  function: (attribute_expression
    attribute: (identifier) @function.call))

(attribute_expression
  attribute: (identifier) @property)

(lambda_expression
  parameter: (identifier) @variable.parameter)

(rewrite_expression
  name: (identifier) @label)

(goal_expression
  name: (identifier) @label)

; ---------------- literals ----------------

(integer) @number
(nat) @number
(float) @number.float
(char) @character
(string) @string
(module_path) @string
(quantity) @constant
(hole) @variable

; ---------------- keywords ----------------

[
  "import"
  "as"
  "type"
  "is"
  "def"
  "law"
  "for"
  "where"
  "exs"
  "match"
  "case"
  "do"
  "return"
] @keyword

; ---------------- operators ----------------

[
  ";"
  "->"
  "||"
  "&&"
  "<"
  "<="
  ">"
  ">="
  "=="
  "!="
  "|"
  "&"
  "<&>"
  "<>"
  "++"
  "+"
  "-"
  "*"
  "/"
  "%"
  ".&."
  ".|."
  ".^."
  "<<"
  "=>"
  "<-"
  "="
  "?"
  "!"
  "@"
  "~"
  "."
  ","
  ".."
] @operator

; ---------------- punctuation ----------------

[
  "("
  ")"
  "["
  "]"
  "{"
  "}"
] @punctuation.bracket

":" @punctuation.delimiter

; ---------------- fallback ----------------

(identifier) @variable
