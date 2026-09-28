; Extension on top of tree-sitter-bash's own queries/highlights.scm.
; The official query covers strings, command names, variables, keywords, comments,
; file descriptors, expansions, the operators $ && > >> < | and -x flags. This adds
; what it misses, without depending on nvim-specific predicates.

[ ";" ";;" ";&" ";;&" "&" ] @punctuation.delimiter

[ "(" ")" "{" "}" "[[" "]]" "((" "))" ] @punctuation.bracket

[ "||" "|&" "=" "+=" "=~" "==" "!=" "&>" "&>>" "<&" ">&" ">|" "<<" "<<<" ]
  @operator

[ "!" "until" "select" "elif" "local" "declare" "typeset" "readonly" ]
  @keyword

(number) @number
(test_operator) @operator
(regex) @string.regexp
