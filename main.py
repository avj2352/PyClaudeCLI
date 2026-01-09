
import os
import sys
import boto3
import re
from typing import List, Dict, Optional
import typer
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.prompt import Prompt, Confirm
# from rich.style import Style
# from rich.live import Live
# from rich.text import Text
from rich import print as rprint
import pyperclip
from pathlib import Path
from prompt_toolkit import PromptSession
from prompt_toolkit.formatted_text import HTML
# from prompt_toolkit.styles import Style as PromptStyle

# Initialize Typer app and Rich console
app = typer.Typer()
console = Console()
APP_VERSION = "0.1.0"

# Configuration
class Config:
    MODELS = {
        "sonnet-4.5": {
            "modelId": "us.anthropic.claude-sonnet-4-5-20250929-v1:0",
            "description": "High intelligence and speed"
        },
        "qwen3 30B": {
            "modelId": "qwen.qwen3-coder-30b-a3b-v1:0",
            "description": "Very fast response code assist"
        },
        "sonnet-4": {
            "modelId": "us.anthropic.claude-sonnet-4-20250514-v1:0",
            "description": "Cost optimized anthropic model"
        },
        "opus-4.1": {
            "modelId": "us.anthropic.claude-opus-4-1-20250805-v1:0",
            "description": "Most capable model for complex tasks"
        },
        "deepseek R1": {
            "modelId": "us.deepseek.r1-v1:0",
            "description": "Reasoning focused model"
        },
    }
    DEFAULT_MODEL = "sonnet-4.5"

class ChatSession:
    def __init__(self):
        self.messages: List[Dict] = []
        self.current_model = Config.DEFAULT_MODEL
        self.bedrock_client = boto3.client(service_name="bedrock-runtime", region_name="us-east-1")
        self.attachments: List[tuple[str, str]] = [] # (filename, content)
        self.last_response: Optional[str] = None
        self.last_code_blocks: List[str] = []
        self.prompt_session = PromptSession()

        # Token and model usage tracking
        self.total_input_tokens: int = 0
        self.total_output_tokens: int = 0
        self.model_usage: Dict[str, int] = {}

        # Load skills content
        self.skills_content: str = self.load_skills()

    def load_skills(self) -> str:
        """Load all markdown files from the skills folder and combine their content."""
        skills_dir = Path("skills")
        if not skills_dir.exists():
            return ""

        combined_skills = ""
        for skill_file in sorted(skills_dir.glob("*.md")):
            try:
                content = skill_file.read_text(encoding='utf-8')
                combined_skills += f"\n\n--- Skill: {skill_file.name} ---\n{content}\n"
            except Exception as e:
                rprint(f"[yellow]Warning: Could not read {skill_file.name}: {e}[/yellow]")

        return combined_skills

    def list_skills(self):
        """List all markdown files in the skills folder."""
        skills_dir = Path("skills")
        if not skills_dir.exists():
            rprint("[yellow]Skills folder does not exist.[/yellow]")
            return

        skill_files = list(skills_dir.glob("*.md"))
        if not skill_files:
            rprint("[yellow]🖇️ No skill files found in the skills folder.[/yellow]")
            return

        rprint("[bold cyan]Available Skills:[/bold cyan]")
        for skill_file in sorted(skill_files):
            rprint(f"  • {skill_file.name}")

    def add_user_message(self, content: str):
        msg_content = [{"text": content}]

        # Add skills content as context
        if self.skills_content:
            msg_content[0]["text"] = f"{self.skills_content}\n\n{content}"

        # Add attachments if any
        if self.attachments:
            file_context = "\n\nAttached Files:\n"
            for name, body in self.attachments:
                file_context += f"--- BEGIN FILE: {name} ---\n{body}\n--- END FILE: {name} ---\n"

            msg_content[0]["text"] += file_context
            self.attachments = [] # Clear attachments after sending

        self.messages.append({"role": "user", "content": msg_content})

    def add_assistant_message(self, content: str):
        self.messages.append({"role": "assistant", "content": [{"text": content}]})
        self.last_response = content
        self.extract_code_blocks(content)

    def extract_code_blocks(self, text: str):
        # Regex to find code blocks: ```language\ncontent``` or ```\ncontent```
        # Captures content between ``` and ```
        pattern = r"```[\w]*\n(.*?)```"
        self.last_code_blocks = re.findall(pattern, text, re.DOTALL)

    def switch_model(self):
        models = list(Config.MODELS.keys())
        rprint(f"[bold cyan]Available Models:[/bold cyan]")
        for idx, model in enumerate(models):
            desc = Config.MODELS[model]["description"]
            rprint(f"{idx + 1}. {model} - [dim]{desc}[/dim]")

        choice = Prompt.ask("Select a model", choices=[str(i+1) for i in range(len(models))], default="1")
        self.current_model = models[int(choice) - 1]
        rprint(f"[green]Switched to {self.current_model}[/green]")

    def inspect_path(self, path_str: str):
        path = Path(path_str)
        if not path.exists():
            rprint(f"[red]Path '{path_str}' does not exist.[/red]")
            return

        if path.is_file():
            try:
                try:
                    content = path.read_text(encoding='utf-8')
                except UnicodeDecodeError:
                    content = "<Binary File>"

                self.attachments.append((path.name, content))
                rprint(f"[green]Attached file: {path.name}[/green]")
            except Exception as e:
                rprint(f"[red]Error reading file: {e}[/red]")
        elif path.is_dir():
            # For directories, we'll list contents and maybe ask to attach all?
            # For now, let's just list and allow picking or attaching all text files (careful with size)
            # Implementation: Attach all text files in the root of the folder (non-recursive for safety)
            confirmation = Confirm.ask(f"Do you want to attach all text files in '{path.name}'?")
            if confirmation:
                count = 0
                for item in path.iterdir():
                    if item.is_file():
                        try:
                            # Simple check for text extension or try read
                            if item.suffix in ['dockerfile', 'Dockerfile', '.rs', '.ts', '.tsx', '.py', '.txt', '.md', '.json', '.yaml', '.yml', '.toml', '.html', '.css', '.scss', '.js']:
                                content = item.read_text(encoding='utf-8')
                                self.attachments.append((item.name, content))
                                count += 1
                        except:
                            pass
                rprint(f"[green]Attached {count} files from {path_str}[/green]")
            else:
                 rprint("[yellow]Operation cancelled.[/yellow]")

    def copy_last_response(self):
        if self.last_response:
            pyperclip.copy(self.last_response)
            rprint("[green]Last response copied to clipboard![/green]")
        else:
            rprint("[yellow]No response to copy.[/yellow]")

    def copy_code_block(self, parts: List[str]):
        if not self.last_code_blocks:
             rprint("[red]No code blocks found in the last response.[/red]")
             return

        index = 0
        if len(parts) < 2:
             if len(self.last_code_blocks) == 1:
                 index = 0
             else:
                 rprint(f"[yellow]Usage: /code <1-{len(self.last_code_blocks)}>[/yellow]")
                 return
        else:
            try:
                index = int(parts[1]) - 1
            except ValueError:
                rprint("[red]Invalid number.[/red]")
                return

        if 0 <= index < len(self.last_code_blocks):
            code = self.last_code_blocks[index]
            pyperclip.copy(code)
            rprint(f"[green]Code block {index + 1} copied to clipboard![/green]")
        else:
            rprint("[red]Invalid code block number.[/red]")

    # intro text
    def chat_loop(self):
        ascii_art = r"""
    ____        ________                __     ________    ____
   / __ \__  __/ ____/ /___ ___  ______/ /__  / ____/ /   /  _/
  / /_/ / / / / /   / / __ `/ / / / __  / _ \/ /   / /    / /
 / ____/ /_/ / /___/ / /_/ / /_/ / /_/ /  __/ /___/ /____/ /
/_/    \__, /\____/_/\__,_/\__,_/\__,_/\___/\____/_____/___/
      /____/
        """
        rprint(Panel.fit(f"\n[bold cyan]{ascii_art}[/bold cyan]\n"
                        "\n[bold magenta]✨Welcome to PyClaudeCLI - a claude clone using aws bedrock✨[/bold magenta]\n"
                        f"[bold cyan]v{APP_VERSION}[/bold cyan]\n"
                        "Commands: /help, /model, /attach <path>, /copy, /code <n>, /skills, /clear, /quit",
                        border_style="magenta"))



        while True:
            try:
                # Show pending attachments in prompt if any
                prompt_suffix = ""
                if self.attachments:
                    prompt_suffix = f" <yellow>({len(self.attachments)} files attached)</yellow>"

                # Using prompt_toolkit for input
                user_input = self.prompt_session.prompt(HTML(f"\n<b><cyan>You</cyan></b>{prompt_suffix}: "))

                if not user_input.strip():
                    continue

                # Handle Slash Commands
                if user_input.startswith("/"):
                    parts = user_input.split()
                    command = parts[0].lower()

                    if command == "/quit":
                        self.show_usage_summary()
                        rprint("[bold red]Goodbye![/bold red]")
                        break
                    elif command == "/model":
                        self.switch_model()
                        continue
                    elif command == "/attach":
                        if len(parts) > 1:
                            self.inspect_path(parts[1])
                        else:
                            rprint("[red]Usage: /attach <path>[/red]")
                        continue
                    elif command == "/copy":
                        self.copy_last_response()
                        continue
                    elif command == "/code":
                        self.copy_code_block(parts)
                        continue
                    elif command == "/clear":
                        self.messages = []
                        self.attachments = []
                        self.last_code_blocks = []
                        self.total_input_tokens = 0
                        self.total_output_tokens = 0
                        self.model_usage = {}
                        rprint("[green]Conversation and usage stats cleared.[/green]")
                        continue
                    elif command == "/skills":
                        self.list_skills()
                        continue
                    elif command == "/help":
                         rprint(Panel("[bold]Available Commands:[/bold]\n"
                                      "/model - Switch AI Model\n"
                                      "/attach <path> - Attach file or directory contents\n"
                                      "/copy - Copy last response to clipboard\n"
                                      "/code <n> - Copy detected code block #n\n"
                                      "/skills - List available skill files\n"
                                      "/clear - Clear conversation history\n"
                                      "/quit - Exit", title="Help"))
                         continue

                # Process Message
                with console.status(f"[bold green]Claude ({self.current_model}) is thinking...[/bold green]"):
                    self.add_user_message(user_input)

                    try:
                        model_id = Config.MODELS[self.current_model]["modelId"]
                        # Handling Bedrock not being set up or error
                        try:
                             response = self.bedrock_client.converse(
                                modelId=model_id,
                                messages=self.messages,
                                inferenceConfig={"maxTokens": 4096, "temperature": 0.7}
                            )
                        except Exception as e:
                             # Fallback or specific error handling
                             raise e

                        output_message = response['output']['message']
                        response_text = output_message['content'][0]['text']

                        # Track token usage
                        usage = response.get('usage', {})
                        input_tokens = usage.get('inputTokens', 0)
                        output_tokens = usage.get('outputTokens', 0)
                        self.total_input_tokens += input_tokens
                        self.total_output_tokens += output_tokens

                        # Track model usage
                        if self.current_model not in self.model_usage:
                            self.model_usage[self.current_model] = 0
                        self.model_usage[self.current_model] += 1

                        self.add_assistant_message(response_text)

                        # Render markdown
                        rprint(f"\n[bold magenta]Claude ({self.current_model}):[/bold magenta]")
                        console.print(Markdown(response_text))

                        # Notify about code blocks
                        if self.last_code_blocks:
                            msg = f"[dim]Found {len(self.last_code_blocks)} code blocks. Use /code"
                            if len(self.last_code_blocks) > 1:
                                msg += " <number>"
                            msg += " to copy.[/dim]"
                            rprint(msg)

                    except Exception as e:
                        rprint(f"[bold red]Error:[/bold red] {e}")

            except KeyboardInterrupt:
                self.show_usage_summary()
                rprint("\n[bold red]Goodbye![/bold red]")
                break

    def show_usage_summary(self):
        """Display a summary panel with token and model usage statistics."""
        if not self.model_usage:
            # No API calls were made
            return

        # Build model usage string
        model_usage_str = ""
        for model, count in self.model_usage.items():
            model_usage_str += f"  • {model}: {count} request{'s' if count != 1 else ''}\n"

        summary = (
            f"[bold cyan]Session Summary[/bold cyan]\n\n"
            f"[bold]Model Usage:[/bold]\n{model_usage_str}\n"
            f"[bold]Token Usage:[/bold]\n"
            f"  • Total Input Tokens: {self.total_input_tokens:,}\n"
            f"  • Total Output Tokens: {self.total_output_tokens:,}\n"
            f"  • Total Tokens: {self.total_input_tokens + self.total_output_tokens:,}"
        )

        rprint("\n")
        rprint(Panel(summary, border_style="cyan", title="💡 Usage Statistics", title_align="left"))

@app.command()
def start():
    """Start the Claude CLI Chat."""
    try:
        session = ChatSession()
        session.chat_loop()
    except Exception as e:
        rprint(f"[bold red]Failed to start session:[/bold red] {e}")
        rprint("[yellow]Ensure AWS credentials are configured correctly.[/yellow]")

if __name__ == "__main__":
    app()
