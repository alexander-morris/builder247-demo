"""Interactive prompt handler for container operations."""
import os
import sys
import logging
from pathlib import Path

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler('/app/logs/prompt.log'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

class PromptHandler:
    """Handles interactive prompt commands."""
    
    def __init__(self):
        """Initialize the prompt handler."""
        self.base_path = Path('/app')
        self.commands = {
            'create': self.create_file,
            'verify': self.verify_file,
            'list': self.list_files,
            'help': self.show_help,
            'exit': self.exit_prompt
        }
        
        # Create necessary directories
        self.base_path.mkdir(exist_ok=True)
        (self.base_path / 'logs').mkdir(exist_ok=True)
        (self.base_path / 'conversations').mkdir(exist_ok=True)
    
    def create_file(self, args):
        """Create a file with specified content."""
        if not args:
            print("Error: Filename required")
            logger.error("Create command called without filename")
            return
            
        filename = args[0]
        content = ' '.join(args[1:]) if len(args) > 1 else ''
        
        file_path = self.base_path / filename
        try:
            file_path.write_text(content)
            message = f"Created file: {file_path}"
            print(message)
            logger.info(message)
        except Exception as e:
            error = f"Error creating file {filename}: {str(e)}"
            print(error)
            logger.error(error)
    
    def verify_file(self, args):
        """Verify a file exists and show its content."""
        if not args:
            print("Error: Filename required")
            logger.error("Verify command called without filename")
            return
            
        filename = args[0]
        file_path = self.base_path / filename
        
        if file_path.exists():
            try:
                content = file_path.read_text()
                print(f"File exists: {file_path}")
                print(f"Content: {content}")
                logger.info(f"Verified file: {file_path}")
            except Exception as e:
                error = f"Error reading file {filename}: {str(e)}"
                print(error)
                logger.error(error)
        else:
            message = f"File not found: {file_path}"
            print(message)
            logger.warning(message)
    
    def list_files(self, args):
        """List files in the base directory."""
        print(f"Contents of {self.base_path}:")
        try:
            for item in self.base_path.iterdir():
                if item.is_file():
                    print(f"- {item.name}")
            logger.info("Listed files in base directory")
        except Exception as e:
            error = f"Error listing files: {str(e)}"
            print(error)
            logger.error(error)
    
    def show_help(self, args):
        """Show available commands."""
        print("Available commands:")
        print("  create <filename> [content] - Create a file with optional content")
        print("  verify <filename> - Verify a file exists and show its content")
        print("  list - List files in the base directory")
        print("  help - Show this help message")
        print("  exit - Exit the prompt")
        logger.info("Showed help message")
    
    def exit_prompt(self, args):
        """Exit the prompt."""
        print("Exiting prompt...")
        logger.info("Exiting prompt")
        sys.exit(0)
    
    def run(self):
        """Run the interactive prompt."""
        print("Welcome to the container prompt")
        logger.info("Started prompt handler")
        
        while True:
            try:
                command = input("(container) ").strip()
                if not command:
                    continue
                    
                parts = command.split()
                cmd = parts[0].lower()
                args = parts[1:]
                
                if cmd in self.commands:
                    self.commands[cmd](args)
                else:
                    print(f"Unknown command: {cmd}")
                    print("Type 'help' for available commands")
                    logger.warning(f"Unknown command attempted: {cmd}")
            
            except KeyboardInterrupt:
                print("\nExiting prompt...")
                logger.info("Prompt interrupted by user")
                sys.exit(0)
            except Exception as e:
                error = f"Error processing command: {str(e)}"
                print(error)
                logger.error(error)

if __name__ == '__main__':
    handler = PromptHandler()
    handler.run() 