import telebot
import os

TOKEN = os.environ.get('BOT_TOKEN')
bot = telebot.TeleBot(TOKEN)

@bot.message_handler(commands = ['start'])
def start(message):
    bot.send_message(message.chat.id, 'ботяра')

bot.polling(non_stop=True)
