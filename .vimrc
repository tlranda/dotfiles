" Colorscheme of basic vim elements
colorscheme desert

" Settings
set scrolloff=8
set ruler
set number
set relativenumber
set tabstop=4 softtabstop=4
set shiftwidth=4
set expandtab
set smartindent
set colorcolumn=80
" Items I carry over from my old vimrc
set hlsearch
highlight StatusLine cterm=bold
highlight ExtraWhitespace ctermbg=red guibg=red
match ExtraWhitespace /\s\+$/
highlight Normal ctermfg=lightgrey ctermbg=black
highlight Comment ctermfg=lightgreen
highlight Special ctermfg=blue
highlight Nontext ctermfg=red

" Open files where you previously closed them
if has("autocmd")
	au BufReadPost * if line("'\"") > 0 && line("'\"") <= line("$")
				\| exe "normal! g'\"" | endif
endif

" Plugins
" Initialize it and list any plugins to fetch/activate
call plug#begin('~/.vim/plugged')
" List plugins with Plug commands (ie: Plug 'tpope/vim-sensible')
Plug 'junegunn/fzf', { 'do': { -> fzf#install() } }
Plug 'junegunn/fzf.vim' " Provides fuzzy-file-finder via :GFiles
Plug 'vim-airline/vim-airline' " Provides better status line
call plug#end()
" :PlugInstall installs plugins
" :PlugUpdate  installs/updates plugins
" :PlugDiff    reviews changes from last update
" :PlugClean   removes plugins no longer in the list

" Remaps
" Designate a variable (leader aka SPACE key)
let mapleader = " "
" When in normal mode, remap " pv" --> :Vex<CR>, aka open Netrw in vertical split
nnoremap <leader>pv :Vex<CR>
" When in normal mode, remap " <CR>" --> resourcing vimrc
nnoremap <leader><CR> :so ~/.vimrc<CR>
" Better access to fuzzy file search
nnoremap <leader><C-f> :GFiles<CR>

" Marks aren't set in this file but reminder for setting/using them:
" m[A-Z] sets a mark on the current file
" Switch to marked file via '[A-Z] for a previously marked file
" Remove mark with command :delmark [A-Z] (remove multiple with
" space-delimited markers)

" Execute directly in shell with grep
" grep <GREP_FOR> <GREP_PATHS>
" You can use :cnext and :cprev to browse results (also :copen)
" Recommended remaps that I did not set up yet:
" nnoremap <C-{k,j,E}> :c{next,prev,open}<CR>

