# Model citation

| | |
|---|---|
| Model | Qwen2.5-3B-Instruct (Qwen Team, Alibaba Cloud, 2024) |
| Installed tag | `qwen2.5:3b` (Ollama library), digest `357c53fb659c` |
| Size | 3.1B parameters, Q4_K_M quantization, 1.93 GB, 32,768-token context |
| Runtime | Ollama 0.40.15, local, NVIDIA RTX 5070 Ti laptop GPU |
| License | Qwen Research License Agreement (Sept 19, 2024), as shipped with the model |
| Source | https://ollama.com/library/qwen2.5 and https://huggingface.co/Qwen/Qwen2.5-3B-Instruct |
| Paper | Qwen Team, "Qwen2.5 Technical Report", arXiv:2412.15115, 2024 |

## Role in Ripple Radar

The model does one job: it reads each event message and returns structured incidents (kind, plant, part, supplier, dates, lot) as JSON. It is called once per message, with one retry that includes the exact validation errors if its first answer fails a check.

Everything after reading is deterministic Python: name and date resolution, graph traversal, scheduling, notifications, loaners, quality holds, policy checks and execution. The model never chooses an action, an order, a slot or a loaner.

## Other models

None. The submitted run (`action_log.jsonl`) used only `qwen2.5:3b` through Ollama on this machine. No hosted or online model was called, and no API key is used.

Measured on the 15 supplied events: 15/15 read correctly on the first attempt, median 2.6 s per message.
