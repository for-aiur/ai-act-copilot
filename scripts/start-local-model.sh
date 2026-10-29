#!/bin/sh
# Explicit start helper; also used by the extension's Start local service action.
# Never installs Ollama or downloads a model.
set -eu
project_dir=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
export OLLAMA_HOST="${OLLAMA_HOST:-127.0.0.1:11434}"
case "$OLLAMA_HOST" in
  127.0.0.1:*|localhost:*|\[::1\]:*) ;;
  *) echo "Ollama must bind to a loopback address." >&2; exit 2 ;;
esac
export OLLAMA_NO_CLOUD=1
export OLLAMA_DEBUG=ERROR
export OLLAMA_DEBUG_LOG_REQUESTS=false
export OLLAMA_MAX_LOADED_MODELS=1
if [ "$#" -gt 0 ]; then
  ollama_command=$1
elif [ -x "$project_dir/.tools/ollama/ollama" ]; then
  ollama_command="$project_dir/.tools/ollama/ollama"
else
  ollama_command=ollama
fi
case "$ollama_command" in
  */*)
    if [ ! -x "$ollama_command" ]; then
      echo "Ollama executable not found: $ollama_command. Install Ollama explicitly or configure aiact.ollamaExecutable." >&2
      exit 127
    fi
    ;;
  *)
    if ! ollama_command=$(command -v "$ollama_command"); then
      echo "Ollama is not on PATH. Install it explicitly or configure aiact.ollamaExecutable." >&2
      exit 127
    fi
    ;;
esac
if [ -x /usr/bin/sandbox-exec ]; then
  exec /usr/bin/sandbox-exec -f "$project_dir/scripts/loopback-only.sb" "$ollama_command" serve
fi
exec "$ollama_command" serve
