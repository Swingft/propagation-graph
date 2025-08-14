import os
from pathlib import Path
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials


class GoogleDriveHandler:
    """Google Drive 관련 모든 작업을 처리하는 핸들러."""

    @staticmethod
    def get_credentials():
        """Google Drive API 인증을 처리하고 유효한 자격 증명을 반환합니다."""
        SCOPES = ['https://www.googleapis.com/auth/drive.file']

        project_root = Path(__file__).resolve().parent.parent

        token_path = project_root / "token.json"
        creds_path = project_root / "credentials.json"

        creds = None
        if token_path.exists():
            creds = Credentials.from_authorized_user_file(str(token_path), SCOPES)

        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                if not creds_path.exists():
                    raise FileNotFoundError(f"OAuth credentials file not found at {creds_path}")
                flow = InstalledAppFlow.from_client_secrets_file(str(creds_path), SCOPES)
                creds = flow.run_local_server(port=0)

            with open(token_path, "w") as token_file:
                token_file.write(creds.to_json())
        return creds

    @staticmethod
    def upload_to_drive(local_file_path, file_name, folder_path="generated_files"):
        """
        Google Drive에 파일을 업로드합니다. (중첩 폴더 지원)
        folder_path 예시: "training_set/input_label"
        """
        creds = GoogleDriveHandler.get_credentials()
        service = build('drive', 'v3', credentials=creds)

        parent_id = 'root'  # 기본 상위 폴더는 '내 드라이브'
        for folder_name in folder_path.split('/'):
            if not folder_name: continue

            query = f"name='{folder_name}' and mimeType='application/vnd.google-apps.folder' and '{parent_id}' in parents and trashed=false"
            response = service.files().list(q=query, fields="files(id)").execute()
            folders = response.get('files', [])

            if folders:
                parent_id = folders[0]['id']
            else:
                file_metadata = {'name': folder_name, 'mimeType': 'application/vnd.google-apps.folder',
                                 'parents': [parent_id]}
                folder = service.files().create(body=file_metadata, fields='id').execute()
                parent_id = folder.get('id')
                print(f"📁 Created Google Drive folder: {folder_name}")

        mimetype = 'text/plain'
        if file_name.endswith('.swift'):
            mimetype = 'text/x-swift'
        elif file_name.endswith('.json'):
            mimetype = 'application/json'

        file_metadata = {'name': file_name, 'parents': [parent_id]}
        media = MediaFileUpload(local_file_path, mimetype=mimetype)
        file = service.files().create(body=file_metadata, media_body=media, fields='id').execute()
        print(f"✅ Uploaded to Google Drive: {folder_path}/{file_name}")
        return file.get('id')