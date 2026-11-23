# History & Zsh Options
HISTFILE=~/.zsh_history
HISTSIZE=10000
SAVEHIST=10000
setopt append_history share_history hist_ignore_dups hist_ignore_space
setopt autocd interactive_comments

# Completion System
autoload -Uz compinit
compinit -d ~/.cache/zsh/zcompdump

# Preferred Apps & Wayland Environment
export EDITOR="nvim"
export VISUAL="nvim"
export TERMINAL="kitty"
export BROWSER="zen-browser"

[[ -r ~/.config/themes/current/zsh.sh ]] && source ~/.config/themes/current/zsh.sh

theme() {
    ~/.config/themes/apply.sh "$@" && source ~/.config/themes/current/zsh.sh
}

themes() {
    ~/.config/themes/menu.sh
}

alias wallpaper='~/.config/wallpaper/wallpaper.sh'
alias wallpapers='~/.config/wallpaper/picker.sh'

# Waybar, Niri & Rofi Helpers
alias wb-reload='pkill -x waybar; waybar -c ~/.config/waybar/config.jsonc -s ~/.config/waybar/style.css >/dev/null 2>&1 &'
alias wb-edit='nvim ~/.config/waybar/config.jsonc ~/.config/waybar/style.css'
alias niri-edit='nvim ~/.config/niri/config.kdl'
alias kitty-edit='nvim ~/.config/kitty/kitty.conf'
alias rofi-edit='nvim ~/.config/rofi/config.rasi ~/.config/themes/current/rofi.rasi'
alias lock='swaylock --indicator-idle-visible'

# Everyday Quality-of-Life Aliases
alias ll='ls -lh --color=auto'
alias la='ls -lAh --color=auto'
alias grep='grep --color=auto'
alias cp='cp -i'
alias mv='mv -i'
