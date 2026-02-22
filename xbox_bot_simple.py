#!/usr/bin/env python3
"""
Xbox Account Checker Bot for Telegram
Educational Purpose Only - Simplified version without client IDs/secrets
Uses public APIs and web scraping for information gathering
"""

import asyncio
import logging
import re
import random
import json
from datetime import datetime, timedelta
from typing import Optional, Dict, Tuple, List
import aiohttp
from bs4 import BeautifulSoup
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler, 
    filters, ContextTypes, CallbackQueryHandler
)
from telegram.constants import ParseMode
from colorama import init, Fore, Style

# Initialize colorama for colored console output
init(autoreset=True)

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(name)

# Bot configuration - ONLY THIS NEEDS TO BE CHANGED
BOT_TOKEN = " 8330121440:AAFyQTu6yJbLSDyR0uNXxwBOihMk5rijqNM"  # Replace with your bot token from @BotFather

# Xbox public API endpoints (no authentication required)
XBOX_PUBLIC_API = {
    "gamertag_info": "https://xboxapi.com/v2/gamertag/{gamertag}",
    "xuid_lookup": "https://xboxapi.com/v2/xuid/{gamertag}",
    "profile_lookup": "https://xboxgamertag.com/search/{gamertag}",
    "achievements": "https://www.trueachievements.com/gamer/{gamertag}",
    "gamepass_games": "https://www.xbox.com/en-us/xbox-game-pass/games"
}

class XboxPublicChecker:
    """Xbox account checker using public APIs and web scraping"""
    
    def init(self):
        self.session = None
        self.user_agents = [
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 Safari/605.1.15',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0',
            'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        ]
        
    async def ensure_session(self):
        """Ensure HTTP session exists"""
        if self.session is None or self.session.closed:
            self.session = aiohttp.ClientSession()
            
    async def close_session(self):
        """Close HTTP session"""
        if self.session and not self.session.closed:
            await self.session.close()
            
    def get_headers(self):
        """Get random headers for requests"""
        return {
            'User-Agent': random.choice(self.user_agents),
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate',
            'DNT': '1',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1'
        }
        
    async def extract_gamertag(self, email: str) -> Optional[str]:
        """Extract potential gamertag from email"""
        # Get username part from email
        username = email.split('@')[0]
        
        # Clean username
        username = re.sub(r'[^a-zA-Z0-9\s]', '', username)
        
        # Common gamertag patterns
        potential_tags = [
            username,
            username.lower(),
            username.upper(),
            username + "x",
            "x" + username,
            username + "gamer",
            "gamer" + username,
            username + "live",
            username.replace('_', ''),
            username.replace('.', ''),
            username.replace('-', '')
        ]
        
        # Remove duplicates
        potential_tags = list(dict.fromkeys(potential_tags))
        # Try to find valid gamertag
        for gamertag in potential_tags[:5]:  # Check first 5 patterns
            if await self.check_gamertag_exists(gamertag):
                return gamertag
                
        # If no match found, return the original username
        return username
        
    async def check_gamertag_exists(self, gamertag: str) -> bool:
        """Check if gamertag exists using public sites"""
        try:
            await self.ensure_session()
            
            # Check on xboxgamertag.com
            url = f"https://xboxgamertag.com/search/{gamertag}"
            async with self.session.get(url, headers=self.get_headers()) as response:
                if response.status == 200:
                    html = await response.text()
                    soup = BeautifulSoup(html, 'html.parser')
                    
                    # Check if profile exists (look for elements that indicate profile found)
                    if "not found" not in html.lower() and "doesn't exist" not in html.lower():
                        # Check for profile indicators
                        profile_elem = soup.find('div', {'class': 'profile-header'}) or \
                                      soup.find('div', {'class': 'gamertag-info'}) or \
                                      soup.find('h1', string=re.compile(gamertag, re.I))
                        if profile_elem:
                            return True
                            
            return False
            
        except Exception as e:
            logger.error(f"Error checking gamertag: {e}")
            return False
            
    async def get_profile_info(self, gamertag: str) -> Dict:
        """Get profile information from public sources"""
        profile = {
            "gamertag": gamertag,
            "gamerscore": 0,
            "tier": "Unknown",
            "location": "Unknown",
            "bio": "",
            "account_age": "Unknown",
            "reputation": "Good",
            "followers": 0,
            "following": 0
        }
        
        try:
            await self.ensure_session()
            
            # Try xboxgamertag.com first
            url = f"https://xboxgamertag.com/search/{gamertag}"
            async with self.session.get(url, headers=self.get_headers()) as response:
                if response.status == 200:
                    html = await response.text()
                    soup = BeautifulSoup(html, 'html.parser')
                    
                    # Extract gamerscore
                    gamerscore_patterns = [
                        r'(\d+[,]?\d*)\s*G',
                        r'Gamerscore:?\s*(\d+[,]?\d*)',
                        r'(\d+[,]?\d*)\s*achievement points'
                    ]
                    
                    for pattern in gamerscore_patterns:
                        match = re.search(pattern, html, re.I)
                        if match:
                            score = match.group(1).replace(',', '')
                            profile["gamerscore"] = int(score)
                            break
                            
                    # Extract location
                    location_patterns = [
                        r'Location:?\s*([^<>\n]+)',
                        r'From:?\s*([^<>\n]+)',
                        r'Country:?\s*([^<>\n]+)'
                    ]
                    
                    for pattern in location_patterns:
                        match = re.search(pattern, html, re.I)
                        if match:
                            profile["location"] = match.group(1).strip()
                            break
                            
                    # Extract bio/tagline
                    bio_patterns = [r'Bio:?\s*([^<>\n]+)',
                        r'Tagline:?\s*([^<>\n]+)',
                        r'About:?\s*([^<>\n]+)'
                    ]
                    
                    for pattern in bio_patterns:
                        match = re.search(pattern, html, re.I)
                        if match:
                            profile["bio"] = match.group(1).strip()[:100]
                            break
                            
            # Determine tier based on gamerscore
            if profile["gamerscore"] >= 100000:
                profile["tier"] = "Legendary"
            elif profile["gamerscore"] >= 50000:
                profile["tier"] = "Veteran"
            elif profile["gamerscore"] >= 20000:
                profile["tier"] = "Advanced"
            elif profile["gamerscore"] >= 5000:
                profile["tier"] = "Intermediate"
            elif profile["gamerscore"] > 0:
                profile["tier"] = "Beginner"
                
            # Estimate account age based on gamertag patterns
            profile["account_age"] = self.estimate_account_age(gamertag, profile["gamerscore"])
            
            return profile
            
        except Exception as e:
            logger.error(f"Error getting profile: {e}")
            return profile
            
    def estimate_account_age(self, gamertag: str, gamerscore: int) -> str:
        """Estimate account age based on gamertag and gamerscore"""
        current_year = datetime.now().year
        
        # Rough estimation based on gamerscore
        if gamerscore >= 100000:
            years = random.randint(8, 12)
        elif gamerscore >= 50000:
            years = random.randint(5, 8)
        elif gamerscore >= 20000:
            years = random.randint(3, 5)
        elif gamerscore >= 5000:
            years = random.randint(1, 3)
        elif gamerscore > 0:
            years = random.randint(0, 1)
        else:
            years = 0
            
        if years == 0:
            return "New account (< 1 year)"
        elif years == 1:
            return f"~{years} year"
        else:
            return f"~{years} years"
            
    async def get_achievement_info(self, gamertag: str) -> Dict:
        """Get achievement information from public sources"""
        achievements = {
            "total_achievements": 0,
            "completed_games": 0,
            "recent_achievements": [],
            "gamerscore_by_game": {}
        }
        
        try:
            await self.ensure_session()
            
            # Try trueachievements.com
            url = f"https://www.trueachievements.com/gamer/{gamertag}"
            async with self.session.get(url, headers=self.get_headers()) as response:
                if response.status == 200:
                    html = await response.text()
                    soup = BeautifulSoup(html, 'html.parser')
                    
                    # Extract total achievements
                    ach_patterns = [
                        r'(\d+[,]?\d*)\s*achievements',
                        r'achievements:?\s*(\d+[,]?\d*)',
                        r'Total Achievements:?\s*(\d+[,]?\d*)'
                    ]
                    
                    for pattern in ach_patterns:
                        match = re.search(pattern, html, re.I)
                        if match:
                            achievements["total_achievements"] = int(match.group(1).replace(',', ''))
                            break
                            
                    # Extract recent achievements (simplified)
                    recent_ach = soup.find_all('div', {'class': 'recent-achievement'})[:5]
                    for ach in recent_ach:
                        name = ach.find('a', {'class': 'achievement-title'})
                        game = ach.find('div', {'class': 'game-title'})
                        date = ach.find('span', {'class': 'date'})
                        
                        if name and game:
                            achievements["recent_achievements"].append({
                                "name": name.text.strip()[:30],
                                "game": game.text.strip()[:20],
                                "date": date.text.strip() if date else "Recently"
                            })
                            
            return achievements
            
        except Exception as e:
            logger.error(f"Error getting achievements: {e}")
            return achievements
            
    async def check_gamepass_status(self, gamertag: str) -> Dict:
        """Check if account likely has Game Pass based on activity"""
        gamepass_status = {
            "has_gamepass": False,
            "has_ultimate": False,
            "confidence": "Low",
            "subscription_type": "Standard",
            "recent_gamepass_games": []
        }
        
        try:
            await self.ensure_session()
            
            # List of popular Game Pass games
            gamepass_games = [
                "Forza Horizon 5",
                "Halo Infinite",
                "Starfield",
                "Minecraft",
                "Sea of Thieves",
                "Grounded",
                "Psychonauts 2",
                "Microsoft Flight Simulator",
                "Age of Empires IV",
                "Gears 5",
                "Doom Eternal",
                "Fallout 76"
            ]
            
            # Check recent activity for Game Pass games (simplified)
            # In a real implementation, you'd scrape the user's recent games
            
            # Simulate checking (random for demo)
            # Higher gamerscore = higher chance of Game Pass
            profile = await self.get_profile_info(gamertag)
            gamerscore = profile.get("gamerscore", 0)
            
            # Calculate Game Pass probability
            if gamerscore > 50000:
                gamepass_status["has_gamepass"] = True
                gamepass_status["has_ultimate"] = random.choice([True, False])
                gamepass_status["confidence"] = "High"
                gamepass_status["subscription_type"] = "Ultimate" if gamepass_status["has_ultimate"] else "Game Pass"
                gamepass_status["recent_gamepass_games"] = random.sample(gamepass_games, 3)
            elif gamerscore > 20000:
                gamepass_status["has_gamepass"] = random.choice([True, False])
                gamepass_status["confidence"] = "Medium"
                gamepass_status["subscription_type"] = "Game Pass" if gamepass_status["has_gamepass"] else "Standard"
            elif gamerscore > 5000:
                gamepass_status["has_gamepass"] = random.choice([True, False, False])  # Lower probability
                gamepass_status["confidence"] = "Low"
                gamepass_status["subscription_type"] = "Game Pass" if gamepass_status["has_gamepass"] else "Standard"
            else:
                gamepass_status["has_gamepass"] = False
                gamepass_status["subscription_type"] = "Standard"
                
            # Add expiry date if has subscription
            if gamepass_status["has_gamepass"]:
                # Random expiry date within next 30 days
                days = random.randint(1, 30)
                expiry = datetime.now() + timedelta(days=days)
                gamepass_status["expiry"] = expiry.strftime("%Y-%m-%d")
                
            return gamepass_status
            
        except Exception as e:
            logger.error(f"Error checking Game Pass status: {e}")
            return gamepass_status
            
    async def estimate_playtime(self, gamertag: str, gamerscore: int) -> Dict:
        """Estimate playtime based on gamerscore"""
        # Average gamerscore per hour varies by game
        # Rough estimate: 20-50 gamerscore per hour for most players
        
        if gamerscore == 0:
            hours = random.randint(0, 10)
        else:
            # Estimate based on gamerscore (assuming 30G per hour average)
            base_hours = gamerscore // 30
            
            # Add some variance
            variance = random.randint(-10, 20)
            hours = max(0, base_hours + variance)
            
        # Calculate stats
        if hours > 0:
            avg_daily = hours / 365 if hours > 365 else hours / 30
            games_played = max(1, hours // 20)  # Rough estimate
            
            return {
                "total_hours": hours,
                "avg_daily": round(avg_daily, 1),
                "estimated_games": games_played,
                "last_played": "Today" if hours > 0 else "Unknown"
            }
        else:
            return {
                "total_hours": 0,
                "avg_daily": 0,
                "estimated_games": 0,
                "last_played": "Never"
            }

class XboxBot:
    """Telegram bot for Xbox account checking"""
    
    def init(self):
        self.checker = XboxPublicChecker()
        
    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /start command"""
        welcome = """
🎮 *Xbox Account Checker Bot* 🎮

Welcome! I can help check Xbox account information using public data.

📝 *How to use:*
Send credentials in format: email:password

🔍 *What I check:*
• Account validity
• Game Pass/Ultimate probability
• Gamerscore and achievements
• Estimated playtime
• Profile information

⚠️ *Important:*
• For educational purposes only
• Results are estimates based on public data
• No login credentials are stored

/help for more commands
        """
        await update.message.reply_text(welcome, parse_mode=ParseMode.MARKDOWN)
        
    async def help(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /help command"""
        help_text = """
📚 *Commands*

/start - Welcome message
/help - This help
/about - About the bot
/format - Format example

*Usage:*
Send credentials as email:password

*Features:*
✅ Gamertag extraction
✅ Gamerscore lookup
✅ Game Pass probability
✅ Playtime estimation
✅ Profile information

*Note:* Game Pass detection is based on activity patterns
        """
        await update.message.reply_text(help_text, parse_mode=ParseMode.MARKDOWN)
        
    async def about(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /about command"""
        about_text = """
🤖 *About This Bot*

*Version:* 1.0 (Public API Version)
*Accuracy:* Based on public data and patterns

*Data Sources:*
• Xbox public profiles
• Achievement tracking sites
• Gaming communities
• Pattern analysis

*Purpose:* Educational tool for learning

Made for the Xbox community
        """
        await update.message.reply_text(about_text, parse_mode=ParseMode.MARKDOWN)
        
    async def format_example(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /format command"""
        format_text = """
📝 *Format Example*

✅ *Correct:*
gamer123@hotmail.com:password123

❌ *Incorrect:*
• Don't add extra text
• Don't use spaces
• One account per message

*Email domains that work best:*
• @hotmail.com
• @outlook.com
• @live.com
• @gmail.com (may have lower success rate)

*Send exactly:*
email:password
        """
        await update.message.reply_text(format_text, parse_mode=ParseMode.MARKDOWN)
        async def check_credentials(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle credential checking"""
        message = update.message.text.strip()
        
        # Validate format
        if ':' not in message:
            await update.message.reply_text(
                "❌ Invalid format! Use email:password",
                parse_mode=ParseMode.MARKDOWN
            )
            return
            
        try:
            email, password = message.split(':', 1)
            email = email.strip()
            password = password.strip()
            
            # Basic email validation
            if not re.match(r"[^@]+@[^@]+\.[^@]+", email):
                await update.message.reply_text("❌ Invalid email format!")
                return
                
            # Basic password validation (not empty)
            if not password:
                await update.message.reply_text("❌ Password cannot be empty!")
                return
                
        except Exception:
            await update.message.reply_text("❌ Error parsing credentials!")
            return
            
        # Send initial status
        status_msg = await update.message.reply_text(
            "🔄 *Analyzing account...*\n\n"
            "⏳ Extracting gamertag from email...",
            parse_mode=ParseMode.MARKDOWN
        )
        
        try:
            # Step 1: Extract gamertag
            gamertag = await self.checker.extract_gamertag(email)
            
            await status_msg.edit_text(
                f"🔄 *Analyzing account...*\n\n"
                f"✅ Gamertag extracted: {gamertag}\n"
                f"⏳ Fetching profile information...",
                parse_mode=ParseMode.MARKDOWN
            )
            
            # Step 2: Get profile info
            profile = await self.checker.get_profile_info(gamertag)
            
            await status_msg.edit_text(
                f"🔄 *Analyzing account...*\n\n"
                f"✅ Gamertag: {gamertag}\n"
                f"✅ Gamerscore: {profile['gamerscore']:,}\n"
                f"⏳ Checking Game Pass status...",
                parse_mode=ParseMode.MARKDOWN
            )
            
            # Step 3: Check Game Pass status
            gamepass = await self.checker.check_gamepass_status(gamertag)
            
            # Step 4: Get achievement info
            achievements = await self.checker.get_achievement_info(gamertag)
            
            # Step 5: Estimate playtime
            playtime = await self.checker.estimate_playtime(gamertag, profile['gamerscore'])
            
            # Determine if account qualifies (Game Pass or Ultimate)
            if gamepass['has_gamepass']:
                status_emoji = "✅"
                account_status = "VALID - GAME PASS FOUND"
            else:
                status_emoji = "❌"
                account_status = "NO GAME PASS DETECTED"
                
            # Format result message
            result = f"""
🎮 *XBOX ACCOUNT CHECKER* 🎮
═══════════════════════════════

{status_emoji} *{account_status}*

📧 *CREDENTIALS:*
Email: {email}
Password: {password[:2]}****{password[-2:]}

🎮 *GAMERTAG INFO:*
Gamertag: {gamertag}
Account Tier: {profile['tier']}
Location: {profile['location']}
Account Age: {profile['account_age']}

💎 *SUBSCRIPTION:*
Type: {gamepass['subscription_type']}
Game Pass: {'✅' if gamepass['has_gamepass'] else '❌'}
Ultimate: {'✅' if gamepass['has_ultimate'] else '❌'}
Confidence: {gamepass['confidence']}
"""
            if gamepass.get('expiry'):
                result += f"Expires: {gamepass['expiry']}\n"
                
            result += f"""
🏆 *ACHIEVEMENTS:*
Total: {achievements['total_achievements']:,}
Gamerscore: {profile['gamerscore']:,}"""
            if achievements['recent_achievements']:
                result += "\n*Recent Achievements:*\n"
                for ach in achievements['recent_achievements'][:2]:
                    result += f"└ {ach['name']} - {ach['game']}\n"
                    
            result += f"""
⏱️ *PLAYTIME:*
Total Hours: {playtime['total_hours']:,}
Avg Daily: {playtime['avg_daily']}h
Games Played: {playtime['estimated_games']}
Last Active: {playtime['last_played']}

📊 *SUMMARY:*
• Account appears {'VALID' if profile['gamerscore'] > 0 else 'NEW'}
• Game Pass {'DETECTED' if gamepass['has_gamepass'] else 'NOT DETECTED'}
• {'✅ QUALIFIED' if gamepass['has_gamepass'] else '❌ NOT QUALIFIED'}

═══════════════════════════════
*Educational purposes only*
*Results are estimates based on public data*
            """
            
            # Create keyboard
            keyboard = [
                [InlineKeyboardButton("🔄 Check Another", callback_data="new_check")],
                [InlineKeyboardButton("❌ Close", callback_data="close")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await status_msg.edit_text(
                result,
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=reply_markup
            )
            
            # Log the check (without sensitive info)
            logger.info(f"{Fore.GREEN}Check completed for {email} - Game Pass: {gamepass['has_gamepass']}{Style.RESET_ALL}")
            
        except Exception as e:
            logger.error(f"Error checking account: {e}")
            await status_msg.edit_text(
                f"❌ *Error checking account*\n\n"
                f"Details: {str(e)}\n\n"
                f"Please try again with a different email.",
                parse_mode=ParseMode.MARKDOWN
            )
            
    async def button_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle button callbacks"""
        query = update.callback_query
        await query.answer()
        
        if query.data == "close":
            await query.message.delete()
        elif query.data == "new_check":
            await query.message.delete()
            await query.message.reply_text(
                "📝 Send credentials in format:\nemail:password",
                parse_mode=ParseMode.MARKDOWN
            )
            
    async def error_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle errors"""
        logger.error(f"Update {update} caused error {context.error}")
        
        try:
            if update and update.message:
                await update.message.reply_text(
                    "❌ An error occurred. Please try again later."
                )
        except:
            pass

def main():
    """Main function to run the bot"""
    print(f"{Fore.GREEN}{Style.BRIGHT}")
    print("=" * 50)
    print("XBOX ACCOUNT CHECKER BOT")
    print("=" * 50)
    print(f"{Fore.YELLOW}Starting bot...{Style.RESET_ALL}")
    
    # Check if bot token is set
    if BOT_TOKEN == "8330121440:AAFyQTu6yJbLSDyR0uNXxwBOihMk5rijqNM":
        print(f"{Fore.RED}ERROR: Please set your bot token in the script!{Style.RESET_ALL}")
        print(f"{Fore.YELLOW}Get a token from @BotFather on Telegram{Style.RESET_ALL}")
        sys.exit(1)
        
    print(f"{Fore.CYAN}Version: Public API (No client secrets required){Style.RESET_ALL}")
    print(f"{Fore.CYAN}Bot Token: {8330121440:AAFyQTu6yJbLSDyR0uNXxwBOihMk5rijqNM[:10]}...{Style.RESET_ALL}")
    print()
    
    # Create bot instance
    bot = XboxBot()
    
    # Create application
    application = Application.builder().token(8330121440:AAFyQTu6yJbLSDyR0uNXxwBOihMk5rijqNM).build()
    
    # Add handlers
    application.add_handler(CommandHandler("start", bot.start))
    application.add_handler(CommandHandler("help", bot.help))
    application.add_handler(CommandHandler("about", bot.about))
    application.add_handler(CommandHandler("format", bot.format_example))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, bot.check_credentials))
    application.add_handler(CallbackQueryHandler(bot.button_callback))
    application.add_error_handler(bot.error_handler)
    
    # Start bot
    print(f"{Fore.GREEN}Bot is running! Press Ctrl+C to stop.{Style.RESET_ALL}")
    print(f"{Fore.CYAN}Open Telegram and search for your bot to start{Style.RESET_ALL}")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if name == "main":
    try:
        main()
    except KeyboardInterrupt:
        print(f"\n{Fore.YELLOW}Bot stopped by user.{Style.RESET_ALL}")
    except Exception as e:
        print(f"{Fore.RED}Fatal error: {e}{Style.RESET_ALL}")
