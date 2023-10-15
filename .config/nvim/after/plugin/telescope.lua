function vim.getVisualSelection()
    vim.cmd('noau normal! "vy"')
    local text = vim.fn.getreg('v')
    vim.fn.setreg('v', {})

    text = string.gsub(text, "\n", "")
    if #text > 0 then
        return text
    else
        return ''
    end
end

local builtin = require('telescope.builtin')
vim.keymap.set('n', '<leader>pf', builtin.find_files, {})
vim.keymap.set('n', 'C-p', builtin.git_files, {})
vim.keymap.set('n', '<leader>ps',function()
    builtin.grep_string({search = vim.fn.input("Grep > ")});
end)

vim.keymap.set('v', '<space>ps', function()
    local text = vim.getVisualSelection()
    builtin.grep_string({ default_text = text })
end)

vim.keymap.set('n', '<leader>po',function()
    builtin.find_files({default_text = vim.fn.expand('%:t:r')});
end)
