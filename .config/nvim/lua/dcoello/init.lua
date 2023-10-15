require("dcoello.remap")
require("dcoello.set")

require('monokai').setup {}
require('nvim_comment').setup()
vim.api.nvim_set_hl(0, 'LineNr', { fg = "#ff4e00", bold=true} )
vim.api.nvim_set_hl(0, 'Blamer', { fg = "#ff4e00", bold=true} )
vim.g.blamer_enabled = true
vim.g.blamer_delay = 500

-- require('nvim-dap-projects').search_project_config()
