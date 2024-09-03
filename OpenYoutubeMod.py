import json
import os
import time

import googleapiclient
import requests
import re
import google.auth
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

# Configuration
SCOPES = ['https://www.googleapis.com/auth/youtube.force-ssl']
BANWORDS_FILE = 'banwords.json'
BANQUESTIONS_FILE = 'banquestions.json'
MODERATORS_FILE = 'moderators.json'

# Sélecteur de langue
def select_language():
    while True:
        language = input("Select your language / Sélectionnez votre langue (EN/FR): ").strip().upper()
        if language in ['EN', 'FR']:
            return language
        print("Invalid choice. Please enter 'EN' or 'FR'. / Choix invalide. Veuillez entrer 'EN' ou 'FR'.")

LANGUAGE = select_language()

# Messages en fonction de la langue
MESSAGES = {
    'FR': {
        'modify_files': 'Pensez à modifier "banquestions.json" et "banwords.json !"',
        'file_created': "'{file}' a été créé : le fichier était manquant ou illisible.",
        'enter_stream_url': "Entrez l'URL de votre stream YouTube : ",
        'invalid_url': "URL invalide ou ID de vidéo non trouvé.",
        'enter_moderator_id': "Entrez l'ID d'un modérateur ou propriétaire (ou appuyez sur Entrée pour terminer) : ",
        'enter_moderator_role': "Entrez le rôle de l'utilisateur avec l'ID {user_id} (modérateur/propriétaire) : ",
        'live_chat_id': 'Live Chat ID: {chat_id}',
        'no_live_chat_id': 'Live chat ID non trouvé ou le stream n’est pas actif.',
        'delete_message_warning': "@{user_name}, merci de ne pas mettre ce genre de mots.",
        'delete_question_warning': "@{user_name}, merci de ne pas posez ce genre de question."
    },
    'EN': {
        'modify_files': 'You can modify "banquestions.json" and "banwords.json !"',
        'file_created': "'{file}' has been created: the file was missing or unreadable.",
        'enter_stream_url': "Enter the URL of your YouTube stream: ",
        'invalid_url': "Invalid URL or video ID not found.",
        'enter_moderator_id': "Enter the ID of a moderator or owner (or press Enter to finish): ",
        'enter_moderator_role': "Enter the role of the user with ID {user_id} (moderator/owner): ",
        'live_chat_id': 'Live Chat ID: {chat_id}',
        'no_live_chat_id': 'Live chat ID not found or the stream is not active.',
        'delete_message_warning': "@{user_name}, please do not use such words.",
        'delete_question_warning': "@{user_name}, please do not ask such questions."
    }
}

def create_default_file(file_path, default_content):
    with open(file_path, 'w') as file:
        json.dump(default_content, file, indent=4)
    print(MESSAGES[LANGUAGE]['file_created'].format(file=file_path))

def load_ban_list(file_path, default_content):
    if not os.path.exists(file_path):
        create_default_file(file_path, default_content)
    try:
        with open(file_path, 'r') as file:
            data = json.load(file)
        return data
    except (json.JSONDecodeError, FileNotFoundError):
        create_default_file(file_path, default_content)
        return default_content

def get_channel_name(youtube, channel_id):
    try:
        response = youtube.channels().list(
            part='snippet',
            id=channel_id
        ).execute()
        items = response.get('items', [])
        if items:
            return items[0]['snippet']['title']
    except Exception as e:
        print(f"Error retrieving channel name: {e}" if LANGUAGE == 'EN' else f"Erreur lors de la récupération du nom du canal : {e}")
    return 'Unknown User' if LANGUAGE == 'EN' else 'Utilisateur inconnu'

def get_youtube_video_id(url):
    youtube_pattern = re.compile(
        r'(?:https?:\/\/)?(?:www\.)?'
        r'(?:youtube\.com\/(?:[^\/\n\s]+\/\S+\/|(?:v|e(?:mbed)?)\/|\S*?[?&]v=)|'
        r'(?:youtu\.be\/))([\w-]{11})')

    match = youtube_pattern.match(url)
    if match:
        return match.group(1)

    try:
        response = requests.get(url)
        html_content = response.text
        match = re.search(r'"videoId":"([a-zA-Z0-9_-]{11})"', html_content)
        if match:
            return match.group(1)
    except Exception as e:
        print(f"Error extracting video ID: {e}" if LANGUAGE == 'EN' else f"Erreur lors de l'extraction de l'ID de vidéo : {e}")

    return None

def create_credentials_file():
    if LANGUAGE == 'EN':
        print("Create a Google Cloud project and download the OAuth 2.0 credentials JSON file.")
        print("Place this file in the same directory as this script and name it 'credentials.json'.")
        print("When you're done, press Enter to continue.")
    else:
        print("Créez un projet Google Cloud et téléchargez le fichier JSON des credentials OAuth 2.0.")
        print("Placez ce fichier dans le même répertoire que ce script et nommez-le 'credentials.json'.")
        print("Lorsque vous avez terminé, appuyez sur Entrée pour continuer.")
    input()

def authenticate_youtube():
    creds = None
    if os.path.exists('token.json'):
        creds = Credentials.from_authorized_user_file('token.json', SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not os.path.exists('credentials.json'):
                create_credentials_file()
            flow = InstalledAppFlow.from_client_secrets_file('credentials.json', SCOPES)
            creds = flow.run_local_server(port=0)
        with open('token.json', 'w') as token:
            token.write(creds.to_json())
    return build('youtube', 'v3', credentials=creds)

def get_live_chat_id(youtube, live_video_id):
    try:
        response = youtube.videos().list(
            part='liveStreamingDetails',
            id=live_video_id
        ).execute()

        items = response.get('items', [])
        if items:
            live_stream_details = items[0].get('liveStreamingDetails', {})
            return live_stream_details.get('activeLiveChatId')
    except Exception as e:
        print(f"Error retrieving Live Chat ID: {e}" if LANGUAGE == 'EN' else f"Erreur lors de la récupération du Live Chat ID : {e}")

    return None

def delete_message(youtube, chat_id, message_id):
    try:
        youtube.liveChatMessages().delete(id=message_id).execute()
    except googleapiclient.errors.HttpError as e:
        print(f"Error deleting message {message_id}: {e}" if LANGUAGE == 'EN' else f"Erreur lors de la suppression du message {message_id}: {e}")

def send_message(youtube, chat_id, text):
    youtube.liveChatMessages().insert(
        part='snippet',
        body={
            'snippet': {
                'liveChatId': chat_id,
                'type': 'textMessageEvent',
                'textMessageDetails': {
                    'messageText': text
                }
            }
        }
    ).execute()

def process_chat_messages(youtube, chat_id, banned_words, banned_questions):
    next_page_token = None
    while True:
        response = youtube.liveChatMessages().list(
            liveChatId=chat_id,
            part='snippet',
            pageToken=next_page_token
        ).execute()

        for message in response['items']:
            snippet = message['snippet']
            print("Message:", snippet)  # Impression pour débogage

            # Récupérer l'ID du message directement à partir du message
            message_id = message.get('id')
            if not message_id:
                print("Aucun 'id' trouvé pour ce message, il sera ignoré.")
                continue  # Passer au message suivant

            message_text = snippet['displayMessage']
            author_channel_id = snippet.get('authorChannelId', 'N/A')

            user_name = get_channel_name(youtube, author_channel_id) if author_channel_id != 'N/A' else 'Utilisateur inconnu'

            if any(word in message_text.lower() for word in banned_words):
                delete_message(youtube, chat_id, message_id)
                response_text = MESSAGES[LANGUAGE]['delete_message_warning'].format(user_name=user_name)
                send_message(youtube, chat_id, response_text)

            elif any(question in message_text.lower() for question in banned_questions):
                delete_message(youtube, chat_id, message_id)
                response_text = MESSAGES[LANGUAGE]['delete_question_warning'].format(user_name=user_name)
                send_message(youtube, chat_id, response_text)

        next_page_token = response.get('nextPageToken')
        if not next_page_token:
            break
        time.sleep(1)  # Attendre avant de vérifier à nouveau les messages

def ask_for_moderators():
    moderators = {}
    while True:
        user_id = input(MESSAGES[LANGUAGE]['enter_moderator_id']).strip()
        if not user_id:
            break
        user_role = input(MESSAGES[LANGUAGE]['enter_moderator_role'].format(user_id=user_id)).strip()
        moderators[user_id] = user_role

    with open(MODERATORS_FILE, 'w') as file:
        json.dump(moderators, file, indent=4)

def main():
    # Définir le contenu par défaut pour les fichiers
    default_banwords = {'banned_words': []}
    default_banquestions = {'banned_questions': []}
    default_moderators = {}

    # Charger les listes de mots bannis et de questions bannies
    banned_words = load_ban_list(BANWORDS_FILE, default_banwords)['banned_words']
    banned_questions = load_ban_list(BANQUESTIONS_FILE, default_banquestions)['banned_questions']

    # Demander l'URL du stream
    stream_url = input(MESSAGES[LANGUAGE]['enter_stream_url']).strip()
    live_video_id = get_youtube_video_id(stream_url)

    if not live_video_id:
        print(MESSAGES[LANGUAGE]['invalid_url'])
        return

    # Demander les ID des modérateurs/propriétaires
    ask_for_moderators()

    # Authentifier et configurer YouTube
    youtube = authenticate_youtube()
    chat_id = get_live_chat_id(youtube, live_video_id)

    if chat_id:
        print(MESSAGES[LANGUAGE]['live_chat_id'].format(chat_id=chat_id))
        while True:
            process_chat_messages(youtube, chat_id, banned_words, banned_questions)
            time.sleep(30)  # Vérifier les messages toutes les 30 secondes
    else:
        print(MESSAGES[LANGUAGE]['no_live_chat_id'])

if __name__ == '__main__':
    print(MESSAGES[LANGUAGE]['modify_files'])
    main()
