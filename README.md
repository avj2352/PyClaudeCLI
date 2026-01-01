# ✨PyClaudeCLI✨

A powerful command-line interface for interacting with advanced AI models via AWS Bedrock. This tool simulates the experience of using Claude and other models directly from your terminal, with features like file attachments, syntax highlighting, and easy code copying.

Whether you need general assistance, coding help, or deep reasoning, this CLI allows you to switch between various state-of-the-art models seamlessly.

## Installation & Usage

### Prerequisites
- Python 3.11+
- AWS Credentials configured (typically in `~/.aws/credentials` or via environment variables) with access to Bedrock models.
- Required Python packages (install via `pip install -r requirements.txt` if you have one, or install individually):
  - `boto3`
  - `typer`
  - `rich`
  - `pyperclip`
  - `prompt_toolkit`

### Running the Application

To start the chat session, run the `main.py` script:

```bash
python main.py
```

Or if you have it installed as a package/entrypoint:
```bash
python main.py start
```

## Available Commands

Once inside the chat session, you can use the following slash commands to interact with the tool:

| Command | Description |
| :--- | :--- |
| `/help` | Show the list of available commands. |
| `/model` | Switch the active AI model. Presents a list of available models to choose from. |
| `/attach <path>` | Attach a file or all text files in a directory to the chat context. |
| `/copy` | Copy the entire text of the last assistant response to the clipboard. |
| `/code <n>` | Copy a specific code block from the last response. Usage: `/code` (for single block) or `/code 1`, `/code 2` etc. |
| `/clear` | Clear the current conversation history and attachments. |
| `/quit` | Exit the application. |

## Supported Models

The application supports a variety of models via AWS Bedrock. You can switch between them using the `/model` command.

| Model Name | Description | ID |
| :--- | :--- | :--- |
| **sonnet-4.5** | High intelligence and speed (Default) | `us.anthropic.claude-sonnet-4-5-20250929-v1:0` |
| **qwen3 30B** | Very fast response code assist | `qwen.qwen3-coder-30b-a3b-v1:0` |
| **sonnet-4** | Cost optimized anthropic model | `us.anthropic.claude-sonnet-4-20250514-v1:0` |
| **opus-4.1** | Most capable model for complex tasks | `us.anthropic.claude-opus-4-1-20250805-v1:0` |
| **deepseek R1** | Reasoning focused model | `us.deepseek.r1-v1:0` |

## Features

- **Rich Markdown Support**: Responses are rendered with proper Markdown formatting, including tables, lists, and syntax highlighting.
- **Code Block Management**: Automatically detects code blocks in responses and allows for easy copying.
- **File Context**: Easily attach files to your prompt to give the AI context for your code or documents.
- **Conversation History**: Maintains context throughout your session (until cleared).

## Testing AWS Bedrock Models

To test the bedrock models you can run the following aws command to invoke converse api

Eg:  using sonnet-4.5 model 

```bash
aws bedrock-runtime invoke-converse --model-id us.anthropic.claude-sonnet-4-5-20250929-v1:0 --input-text "Hello, how are you?"
```

To list all foundation models (with their model ids) available run the following aws command:

```bash
# simple command to list all details
aws bedrock list-foundation-models

# show in table format
aws bedrock list-foundation-models --query 'modelSummaries[*].[modelId,modelName]' --output table
```
