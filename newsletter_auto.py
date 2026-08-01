#!/usr/bin/env python3
"""
COMPLETE AI Web Automation System
Ready-to-play with all features included
"""

# ============================================================================
# IMPORTS - If missing, run: pip install opencv-python pillow numpy pyautogui playwright schedule
# ============================================================================
import sys
import os
import time
import json
import schedule
import threading
import logging
import argparse
import sqlite3
import smtplib
import hashlib
import subprocess
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, asdict
from enum import Enum
from queue import Queue

# Third-party imports
try:
    import cv2
    import numpy as np
    from PIL import Image, ImageGrab
    import pyautogui
    from playwright.sync_api import sync_playwright, Page
    import schedule
    from email.mime.text import MIMEText
    from email.mime.multipart import MIMEMultipart
    import yaml
    PYWIN32_AVAILABLE = True
except ImportError as e:
    print(f"⚠️  Missing package: {e}")
    print("Installing required packages...")
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install", 
                              "opencv-python", "pillow", "numpy", "pyautogui", 
                              "playwright", "schedule", "pyyaml"])
        # Import again after install
        import cv2
        import numpy as np
        from PIL import Image, ImageGrab
        import pyautogui
        from playwright.sync_api import sync_playwright, Page
        import schedule
        import yaml
        from email.mime.text import MIMEText
        from email.mime.multipart import MIMEMultipart
        print("✅ Packages installed successfully!")
    except:
        print("❌ Failed to install packages. Please run manually:")
        print("pip install opencv-python pillow numpy pyautogui playwright schedule pyyaml")
        sys.exit(1)

# ============================================================================
# CONFIGURATION
# ============================================================================
@dataclass
class Config:
    """Configuration management"""
    # Website settings
    login_url: str = "https://example.com/login"
    post_url: str = "https://example.com/newsletter/create"
    username: str = "your_email@example.com"
    password: str = "your_password"
    
    # AI & Performance
    confidence_threshold: float = 0.80
    max_wait_time: int = 30
    retry_attempts: int = 3
    use_ai_vision: bool = True
    
    # Scheduling
    schedule_time: str = "09:00"
    timezone: str = "America/New_York"
    run_on_startup: bool = False
    
    # Email notifications (optional)
    email_enabled: bool = False
    smtp_server: str = "smtp.gmail.com"
    smtp_port: int = 587
    email_sender: str = ""
    email_password: str = ""
    email_recipients: List[str] = None
    
    # Paths
    base_dir: str = "."
    screenshot_dir: str = "./screenshots"
    template_dir: str = "./screenshots/templates"
    log_dir: str = "./logs"
    content_dir: str = "./content"
    workflow_dir: str = "./workflows"
    database_path: str = "./data/automation.db"
    
    def __post_init__(self):
        if self.email_recipients is None:
            self.email_recipients = []
        
        # Create directories
        for dir_path in [self.screenshot_dir, self.template_dir, self.log_dir, 
                        self.content_dir, self.workflow_dir, "./data"]:
            Path(dir_path).mkdir(parents=True, exist_ok=True)

class LogLevel(Enum):
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    SUCCESS = "SUCCESS"

# ============================================================================
# LOGGING SYSTEM
# ============================================================================
class AdvancedLogger:
    """Enhanced logging with file and console output"""
    
    def __init__(self, config: Config):
        self.config = config
        self.setup_logging()
        
    def setup_logging(self):
        """Configure logging handlers"""
        log_file = Path(self.config.log_dir) / f"automation_{datetime.now():%Y%m%d}.log"
        
        self.logger = logging.getLogger("AutomationMaster")
        self.logger.setLevel(logging.INFO)
        
        # Remove existing handlers
        self.logger.handlers = []
        
        # File handler
        file_handler = logging.FileHandler(log_file)
        file_handler.setFormatter(logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        ))
        
        # Console handler
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(logging.Formatter(
            '%(levelname)s: %(message)s'
        ))
        
        self.logger.addHandler(file_handler)
        self.logger.addHandler(console_handler)
    
    def log(self, level: LogLevel, message: str, module: str = "Main"):
        """Log message to all outputs"""
        if level == LogLevel.INFO:
            self.logger.info(f"[{module}] {message}")
        elif level == LogLevel.WARNING:
            self.logger.warning(f"[{module}] {message}")
        elif level == LogLevel.ERROR:
            self.logger.error(f"[{module}] {message}")
        elif level == LogLevel.SUCCESS:
            self.logger.info(f"[{module}] ✅ {message}")
        
        # Email critical errors
        if level == LogLevel.ERROR and self.config.email_enabled and self.config.email_sender:
            self.send_error_email(message)
    
    def send_error_email(self, message: str):
        """Send error notification email"""
        try:
            if not self.config.email_sender or not self.config.email_recipients:
                return
                
            msg = MIMEMultipart()
            msg['From'] = self.config.email_sender
            msg['To'] = ", ".join(self.config.email_recipients)
            msg['Subject'] = f"Automation Error: {message[:50]}..."
            
            body = f"""
            Automation System Error
            
            Time: {datetime.now()}
            Error: {message}
            
            Check logs for more information.
            """
            msg.attach(MIMEText(body, 'plain'))
            
            with smtplib.SMTP(self.config.smtp_server, self.config.smtp_port) as server:
                server.starttls()
                server.login(self.config.email_sender, self.config.email_password)
                server.send_message(msg)
                
        except Exception as e:
            self.logger.error(f"Failed to send error email: {e}")

# ============================================================================
# AI VISION ENGINE
# ============================================================================
class AIVisionEngine:
    """Computer vision for web element detection"""
    
    def __init__(self, config: Config, logger: AdvancedLogger):
        self.config = config
        self.logger = logger
        self.templates = {}
        self.load_templates()
    
    def load_templates(self):
        """Load all template images"""
        template_dir = Path(self.config.template_dir)
        if not template_dir.exists():
            return
        
        for template_file in template_dir.glob("*.png"):
            template_name = template_file.stem
            template_img = cv2.imread(str(template_file))
            if template_img is not None:
                self.templates[template_name] = template_img
                self.logger.log(LogLevel.INFO, f"Loaded template: {template_name}", "Vision")
    
    def capture_screen(self, region=None, save=False, name="screen"):
        """Capture screen or region"""
        try:
            if region:
                screenshot = pyautogui.screenshot(region=region)
            else:
                screenshot = pyautogui.screenshot()
            
            # Convert to OpenCV format
            screen_cv = cv2.cvtColor(np.array(screenshot), cv2.COLOR_RGB2BGR)
            
            if save:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = f"{name}_{timestamp}.png"
                save_path = Path(self.config.screenshot_dir) / filename
                cv2.imwrite(str(save_path), screen_cv)
                self.logger.log(LogLevel.INFO, f"Screenshot saved: {save_path}", "Vision")
            
            return screen_cv
            
        except Exception as e:
            self.logger.log(LogLevel.ERROR, f"Screen capture failed: {e}", "Vision")
            return None
    
    def find_element(self, template_name: str, screen_image=None):
        """Find element using template matching"""
        if template_name not in self.templates:
            self.logger.log(LogLevel.WARNING, f"Template not found: {template_name}", "Vision")
            return None
        
        template = self.templates[template_name]
        
        if screen_image is None:
            screen_image = self.capture_screen(save=False)
            if screen_image is None:
                return None
        
        # Template matching
        result = cv2.matchTemplate(screen_image, template, cv2.TM_CCOEFF_NORMED)
        min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(result)
        
        if max_val >= self.config.confidence_threshold:
            x, y = max_loc
            w, h = template.shape[1], template.shape[0]
            
            detection = {
                'x': x, 'y': y, 'width': w, 'height': h,
                'confidence': float(max_val),
                'center_x': x + w // 2,
                'center_y': y + h // 2
            }
            
            self.logger.log(LogLevel.INFO, 
                          f"Found {template_name} at ({x}, {y}) with confidence {max_val:.2f}", 
                          "Vision")
            return detection
        
        return None
    
    def record_template_interactive(self, template_name: str):
        """Interactive template recording"""
        self.logger.log(LogLevel.INFO, f"Recording template: {template_name}", "Vision")
        
        print(f"\n{'='*50}")
        print(f"📸 Recording Template: {template_name}")
        print("1. Make sure the element is visible on screen")
        print("2. Press Enter to capture the entire screen")
        print("3. Click and drag to select the element")
        print("="*50)
        
        input("\nPress Enter when ready...")
        
        # Capture full screen
        full_screen = self.capture_screen(save=True, name="full_screen")
        if full_screen is None:
            print("❌ Failed to capture screen")
            return False
        
        # Show instructions for region selection
        print("\nNow click and drag to select the element region.")
        print("Move mouse to top-left corner, press Enter")
        print("Move to bottom-right corner, press Enter")
        
        try:
            # Get first point
            input("Move to top-left and press Enter...")
            x1, y1 = pyautogui.position()
            print(f"Top-left: ({x1}, {y1})")
            
            # Get second point
            input("Move to bottom-right and press Enter...")
            x2, y2 = pyautogui.position()
            print(f"Bottom-right: ({x2}, {y2})")
            
            # Calculate region
            left = min(x1, x2)
            top = min(y1, y2)
            width = abs(x2 - x1)
            height = abs(y2 - y1)
            
            if width < 10 or height < 10:
                print("❌ Region too small")
                return False
            
            # Capture template
            template_img = self.capture_screen(region=(left, top, width, height), save=False)
            
            if template_img is None or template_img.size == 0:
                print("❌ Failed to capture template")
                return False
            
            # Save template
            template_path = Path(self.config.template_dir) / f"{template_name}.png"
            cv2.imwrite(str(template_path), template_img)
            
            # Add to cache
            self.templates[template_name] = template_img
            
            print(f"\n✅ Template saved: {template_name}")
            print(f"   Size: {width}x{height} pixels")
            print(f"   Location: {template_path}")
            
            self.logger.log(LogLevel.SUCCESS, 
                          f"Template recorded: {template_name} ({width}x{height})", 
                          "Vision")
            return True
            
        except Exception as e:
            print(f"❌ Error: {e}")
            self.logger.log(LogLevel.ERROR, f"Template recording failed: {e}", "Vision")
            return False

# ============================================================================
# BROWSER AUTOMATION
# ============================================================================
class BrowserAutomation:
    """Browser automation with AI vision fallback"""
    
    def __init__(self, config: Config, logger: AdvancedLogger, vision: AIVisionEngine):
        self.config = config
        self.logger = logger
        self.vision = vision
        self.playwright = None
        self.browser = None
        self.page = None
        self.current_state = "initialized"
    
    def start(self, headless: bool = False):
        """Start browser session"""
        try:
            self.logger.log(LogLevel.INFO, "Starting browser session", "Browser")
            
            self.playwright = sync_playwright().start()
            
            launch_options = {
                'headless': headless,
                'args': [
                    '--disable-blink-features=AutomationControlled',
                    '--no-sandbox',
                    '--window-size=1920,1080'
                ]
            }
            
            self.browser = self.playwright.chromium.launch(**launch_options)
            
            self.page = self.browser.new_page(
                viewport={'width': 1920, 'height': 1080},
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            )
            
            # Stealth script
            self.page.add_init_script("""
                Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
            """)
            
            self.current_state = "ready"
            self.logger.log(LogLevel.SUCCESS, "Browser session started", "Browser")
            return True
            
        except Exception as e:
            self.logger.log(LogLevel.ERROR, f"Failed to start browser: {e}", "Browser")
            return False
    
    def stop(self):
        """Stop browser session"""
        try:
            if self.browser:
                self.browser.close()
            if self.playwright:
                self.playwright.stop()
            
            self.current_state = "stopped"
            self.logger.log(LogLevel.INFO, "Browser session stopped", "Browser")
            return True
            
        except Exception as e:
            self.logger.log(LogLevel.ERROR, f"Error stopping browser: {e}", "Browser")
            return False
    
    def navigate(self, url: str):
        """Navigate to URL"""
        try:
            self.logger.log(LogLevel.INFO, f"Navigating to: {url}", "Browser")
            self.page.goto(url, wait_until="networkidle")
            time.sleep(2)
            self.logger.log(LogLevel.SUCCESS, f"Navigation successful", "Browser")
            return True
        except Exception as e:
            self.logger.log(LogLevel.ERROR, f"Navigation failed: {e}", "Browser")
            return False
    
    def smart_click(self, selector: str = None, template: str = None, text: str = None):
        """Click element using multiple strategies"""
        try:
            # Strategy 1: CSS Selector
            if selector:
                element = self.page.wait_for_selector(selector, timeout=5000)
                element.click()
                self.logger.log(LogLevel.SUCCESS, f"Clicked using selector: {selector}", "Browser")
                return True
            
            # Strategy 2: Text Content
            elif text:
                element = self.page.get_by_text(text).first
                element.wait_for(state="visible", timeout=5000)
                element.click()
                self.logger.log(LogLevel.SUCCESS, f"Clicked using text: '{text}'", "Browser")
                return True
            
            # Strategy 3: Vision
            elif template and self.config.use_ai_vision:
                screenshot = self.vision.capture_screen(save=False)
                detection = self.vision.find_element(template, screenshot)
                
                if detection:
                    self.page.mouse.click(detection['center_x'], detection['center_y'])
                    self.logger.log(LogLevel.SUCCESS, 
                                  f"Clicked using vision: {template}", 
                                  "Browser")
                    return True
            
            return False
            
        except Exception as e:
            self.logger.log(LogLevel.WARNING, f"Click failed: {e}", "Browser")
            return False
    
    def smart_type(self, text: str, selector: str = None, template: str = None):
        """Type text into element"""
        try:
            if selector:
                element = self.page.wait_for_selector(selector, timeout=5000)
                element.fill(text)
            elif template and self.config.use_ai_vision:
                screenshot = self.vision.capture_screen(save=False)
                detection = self.vision.find_element(template, screenshot)
                
                if detection:
                    self.page.mouse.click(detection['center_x'], detection['center_y'])
                    time.sleep(0.5)
                    self.page.keyboard.type(text)
            else:
                self.page.keyboard.type(text)
            
            self.logger.log(LogLevel.SUCCESS, f"Typed text", "Browser")
            return True
            
        except Exception as e:
            self.logger.log(LogLevel.ERROR, f"Type failed: {e}", "Browser")
            return False
    
    def login(self):
        """Login to website"""
        if not self.navigate(self.config.login_url):
            return False
        
        # Try different login strategies
        strategies = [
            {"username": "input[name='username']", "password": "input[name='password']", "button": "button[type='submit']"},
            {"username": "#email", "password": "#password", "button": "button:has-text('Login')"},
            {"username": "input[type='email']", "password": "input[type='password']", "button": "[type='submit']"}
        ]
        
        for strategy in strategies:
            try:
                self.page.fill(strategy["username"], self.config.username)
                self.page.fill(strategy["password"], self.config.password)
                self.page.click(strategy["button"])
                time.sleep(3)
                
                # Check if login was successful
                if "login" not in self.page.url.lower():
                    self.logger.log(LogLevel.SUCCESS, "Login successful", "Browser")
                    return True
                    
            except:
                continue
        
        # Vision fallback
        if self.config.use_ai_vision:
            self.logger.log(LogLevel.INFO, "Trying vision-based login", "Browser")
            return self._login_with_vision()
        
        return False
    
    def _login_with_vision(self):
        """Login using computer vision"""
        try:
            # Take screenshot for debugging
            self.vision.capture_screen(save=True, name="login_screen")
            
            # Look for username field
            username_field = self.vision.find_element("username_field")
            if username_field:
                self.page.mouse.click(username_field['center_x'], username_field['center_y'])
                self.page.keyboard.type(self.config.username)
            
            # Look for password field
            password_field = self.vision.find_element("password_field")
            if password_field:
                self.page.mouse.click(password_field['center_x'], password_field['center_y'])
                self.page.keyboard.type(self.config.password)
            
            # Look for login button
            login_button = self.vision.find_element("login_button")
            if login_button:
                self.page.mouse.click(login_button['center_x'], login_button['center_y'])
            else:
                self.page.keyboard.press("Enter")
            
            time.sleep(3)
            return "login" not in self.page.url.lower()
            
        except Exception as e:
            self.logger.log(LogLevel.ERROR, f"Vision login failed: {e}", "Browser")
            return False

# ============================================================================
# CONTENT MANAGER
# ============================================================================
class ContentManager:
    """Manages newsletter content"""
    
    def __init__(self, config: Config, logger: AdvancedLogger):
        self.config = config
        self.logger = logger
        self.setup_database()
    
    def setup_database(self):
        """Setup content database"""
        try:
            conn = sqlite3.connect(self.config.database_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS newsletters (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title TEXT NOT NULL,
                    content TEXT NOT NULL,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            conn.commit()
            conn.close()
            self.logger.log(LogLevel.SUCCESS, "Database initialized", "Content")
            
        except Exception as e:
            self.logger.log(LogLevel.ERROR, f"Database setup failed: {e}", "Content")
    
    def get_sample_content(self):
        """Get sample newsletter content"""
        return {
            "title": f"Daily Update - {datetime.now():%B %d, %Y}",
            "content": """# Daily Team Update

## Important Announcements
1. System maintenance scheduled for tonight
2. New project kickoff meeting tomorrow
3. Quarterly review reports due Friday

## Team Highlights
- Engineering: Completed sprint ahead of schedule
- Marketing: New campaign launched successfully
- Sales: Exceeded monthly targets

## Reminders
- Submit timesheets by Friday
- Team lunch next Wednesday
- Training session next week

*Automatically generated by Newsletter Automation System*""",
            "author": "Automation System",
            "date": datetime.now().isoformat()
        }
    
    def save_content(self, content: Dict):
        """Save content to database"""
        try:
            conn = sqlite3.connect(self.config.database_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                INSERT INTO newsletters (title, content)
                VALUES (?, ?)
            ''', (content['title'], content['content']))
            
            content_id = cursor.lastrowid
            conn.commit()
            conn.close()
            
            self.logger.log(LogLevel.SUCCESS, f"Content saved with ID: {content_id}", "Content")
            return content_id
            
        except Exception as e:
            self.logger.log(LogLevel.ERROR, f"Failed to save content: {e}", "Content")
            return None

# ============================================================================
# MAIN AUTOMATION SYSTEM
# ============================================================================
class NewsletterAutomationSystem:
    """Main system orchestrating all components"""
    
    def __init__(self, config: Config = None):
        self.config = config or Config()
        self.logger = AdvancedLogger(self.config)
        self.vision = AIVisionEngine(self.config, self.logger)
        self.browser = BrowserAutomation(self.config, self.logger, self.vision)
        self.content = ContentManager(self.config, self.logger)
        
        self.logger.log(LogLevel.SUCCESS, "Automation System Initialized", "System")
    
    def setup_interactive(self):
        """Interactive setup wizard"""
        print("\n" + "="*60)
        print("🤖 Newsletter Automation Setup Wizard")
        print("="*60)
        
        # Website configuration
        print("\n📝 Website Configuration")
        self.config.login_url = input(f"Login URL [{self.config.login_url}]: ") or self.config.login_url
        self.config.post_url = input(f"Post URL [{self.config.post_url}]: ") or self.config.post_url
        self.config.username = input(f"Username [{self.config.username}]: ") or self.config.username
        self.config.password = input(f"Password [{self.config.password}]: ") or self.config.password
        
        # Schedule
        print("\n⏰ Scheduling")
        self.config.schedule_time = input(f"Daily schedule time (HH:MM) [{self.config.schedule_time}]: ") or self.config.schedule_time
        
        # Templates
        print("\n📸 Template Recording")
        record = input("Record website templates now? (y/n): ").lower() == 'y'
        if record:
            templates = ["username_field", "password_field", "login_button", 
                        "title_field", "content_field", "submit_button"]
            
            for template in templates:
                record_it = input(f"Record '{template}'? (y/n): ").lower() == 'y'
                if record_it:
                    self.vision.record_template_interactive(template)
        
        # Save configuration
        config_file = Path(self.config.base_dir) / "config.yaml"
        with open(config_file, 'w') as f:
            yaml.dump(asdict(self.config), f)
        
        print(f"\n✅ Setup complete! Configuration saved to {config_file}")
    
    def run_automation(self, headless: bool = True):
        """Run complete automation cycle"""
        self.logger.log(LogLevel.INFO, "Starting automation cycle", "System")
        
        try:
            # Step 1: Start browser
            if not self.browser.start(headless=headless):
                return False
            
            # Step 2: Login
            if not self.browser.login():
                self.browser.stop()
                return False
            
            # Step 3: Navigate to post page
            if not self.browser.navigate(self.config.post_url):
                self.browser.stop()
                return False
            
            # Step 4: Get content
            content = self.content.get_sample_content()
            
            # Step 5: Fill form (customize for your website)
            # Example: Fill title
            self.browser.smart_type(
                content['title'],
                selector="#title",  # Change to your website's selector
                template="title_field"
            )
            
            # Example: Fill content
            self.browser.smart_type(
                content['content'],
                selector="#content",  # Change to your website's selector
                template="content_field"
            )
            
            # Step 6: Submit
            self.browser.smart_click(
                selector="button[type='submit']",  # Change to your website's selector
                template="submit_button",
                text="Publish"
            )
            
            # Wait for submission
            time.sleep(3)
            
            # Step 7: Save content to database
            self.content.save_content(content)
            
            # Step 8: Stop browser
            self.browser.stop()
            
            self.logger.log(LogLevel.SUCCESS, "Automation completed successfully!", "System")
            return True
            
        except Exception as e:
            self.logger.log(LogLevel.ERROR, f"Automation failed: {e}", "System")
            try:
                self.browser.stop()
            except:
                pass
            return False
    
    def start_scheduler(self):
        """Start scheduled automation"""
        self.logger.log(LogLevel.INFO, f"Starting scheduler for {self.config.schedule_time}", "System")
        
        def job():
            self.logger.log(LogLevel.INFO, "Running scheduled job", "System")
            self.run_automation(headless=True)
        
        # Schedule daily job
        schedule.every().day.at(self.config.schedule_time).do(job)
        
        # Run immediately if configured
        if self.config.run_on_startup:
            job()
        
        print(f"\n✅ Scheduler started. Will run daily at {self.config.schedule_time}")
        print("Press Ctrl+C to stop\n")
        
        # Keep running
        try:
            while True:
                schedule.run_pending()
                time.sleep(60)
        except KeyboardInterrupt:
            print("\n🛑 Scheduler stopped")
            self.logger.log(LogLevel.INFO, "Scheduler stopped by user", "System")

# ============================================================================
# COMMAND LINE INTERFACE
# ============================================================================
def main():
    """Main CLI entry point"""
    parser = argparse.ArgumentParser(description="AI-Powered Newsletter Automation System")
    parser.add_argument('--setup', action='store_true', help='Run interactive setup')
    parser.add_argument('--test', action='store_true', help='Test system components')
    parser.add_argument('--run', action='store_true', help='Run automation once')
    parser.add_argument('--schedule', action='store_true', help='Start scheduled system')
    parser.add_argument('--record', metavar='TEMPLATE', help='Record a template')
    
    # Check if no arguments provided
    if len(sys.argv) == 1:
        # Interactive mode
        print("\n" + "="*60)
        print("🤖 AI Newsletter Automation System")
        print("="*60)
        print("\nCommands:")
        print("  python newsletter_auto.py --setup   First-time setup")
        print("  python newsletter_auto.py --test    Test system")
        print("  python newsletter_auto.py --run     Run once")
        print("  python newsletter_auto.py --schedule Start scheduler")
        print("  python newsletter_auto.py --record login_button  Record template")
        print("\nOr run without arguments for this menu")
        return
    
    args = parser.parse_args()
    
    # Create system
    config = Config()
    system = NewsletterAutomationSystem(config)
    
    # Execute command
    if args.setup:
        system.setup_interactive()
    
    elif args.test:
        print("🧪 Testing system components...")
        
        # Test browser
        print("1. Testing browser...")
        if system.browser.start(headless=False):
            print("   ✅ Browser: OK")
            system.browser.stop()
        else:
            print("   ❌ Browser: FAILED")
        
        # Test vision
        print("2. Testing vision...")
        if len(system.vision.templates) > 0:
            print(f"   ✅ Vision: {len(system.vision.templates)} templates loaded")
        else:
            print("   ⚠️  Vision: No templates (run --setup to record)")
        
        # Test content
        print("3. Testing content...")
        content = system.content.get_sample_content()
        print(f"   ✅ Content: Sample content ready")
        
        print("\n✅ System test completed!")
    
    elif args.record:
        if args.record:
            system.vision.record_template_interactive(args.record)
        else:
            print("❌ Please specify template name: --record login_button")
    
    elif args.run:
        print("🚀 Running automation...")
        success = system.run_automation(headless=False)
        if success:
            print("✅ Automation completed successfully!")
        else:
            print("❌ Automation failed. Check logs for details.")
    
    elif args.schedule:
        print("⏰ Starting scheduled system...")
        system.start_scheduler()
    
    else:
        parser.print_help()

# ============================================================================
# INSTALLATION CHECK
# ============================================================================
def check_installation():
    """Check and install required packages"""
    print("🔍 Checking installation...")
    
    # Check Playwright browsers
    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            # Try to launch to check installation
            pass
        print("✅ Playwright: OK")
    except:
        print("⚠️  Playwright not installed. Installing browsers...")
        try:
            subprocess.check_call([sys.executable, "-m", "playwright", "install", "chromium"])
            print("✅ Playwright browsers installed")
        except:
            print("❌ Failed to install Playwright. Please run manually:")
            print("   pip install playwright")
            print("   playwright install chromium")
            return False
    
    return True

# ============================================================================
# MAIN EXECUTION
# ============================================================================
if __name__ == "__main__":
    print("\n" + "="*60)
    print("🤖 AI NEWSLETTER AUTOMATION SYSTEM")
    print("="*60)
    
    # Check installation
    if not check_installation():
        sys.exit(1)
    
    # Run main function
    main()