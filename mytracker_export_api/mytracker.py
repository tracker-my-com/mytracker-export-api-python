import hashlib
import hmac
import base64
import time
import requests
import pandas as pd
from binascii import b2a_base64
from urllib.parse import urlencode, quote_plus
from urllib.request import urlopen
from .exceptions import MyTrackerError


class MyTracker:
    
    METHOD_GET = 'GET'
    METHOD_POST = 'POST'
    
    CREATE_RAW_DATA_URL = 'https://tracker.my.com/api/raw/v1/export/create.json'
    GET_RAW_DATA_URL = 'https://tracker.my.com/api/raw/v1/export/get.json'
    CANCEL_RAW_DATA_URL = 'https://tracker.my.com/api/raw/v1/export/cancel.json'
    
    CREATE_REPORT_URL = 'https://tracker.my.com/api/report/v1/file/create.json'
    GET_REPORT_URL = 'https://tracker.my.com/api/report/v1/file/get.json'
    
    CREATE_SEGMENT_URL = 'https://tracker.my.com/api/segment/v1/export/create.json'
    GET_SEGMENT_URL = 'https://tracker.my.com/api/segment/v1/export/get.json'
    
    
    def __init__(self, api_user_id, api_secret_key):
        self.api_user_id = api_user_id
        self.api_secret_key = api_secret_key
    
    def _get_signature(self, url, method, data='') -> str:
        ''' Getting a signature. '''
        
        base_string = '&'.join([method.upper(), quote_plus(url, safe='~'), quote_plus(data, safe='~')])
        signature = base64.b64encode(hmac.new(bytes(self.api_secret_key, 'UTF-8'), 
                                              bytes(base_string, 'UTF-8'), 
                                              hashlib.sha1).digest())
        signature = str(signature, 'UTF-8').rstrip('\n')
        return f'AuthHMAC {self.api_user_id}:{signature}'

    def _send_request(self, url, method, headers=None):
        ''' Sending a request. '''
        
        if not headers:
            headers = {}
        headers['Authorization'] = self._get_signature(url, method)
        if method.upper() == 'GET':
            return requests.get(url=url, headers=headers)
        elif method.upper() == 'POST':
            return requests.post(url=url, headers=headers)
    
    def create_export(self, create_params, url):
        ''' 
        Data export request. 

        -----------
        Parameters:
            create_params (dict): a dictionary with data export parameters
            url (str): API endpoint to send request

        Example:
            create_params = {
                'dateFrom': '2022-05-01',
                'dateTo': '2022-05-31',
                'selectors': 'idAdEventTypeTitle,tsClick,tsView,dtEvent,tsEvent,idPartnerTitle,advertisingId',
                'idApp': 1,  
                'event': 'installs'
            }
            
            If you want to get data for multiple apps (accounts, etc.), 
            then add square brackets to the key 'idApp[]': [1, 2, 3],
            or specify the desired values in the string separated by commas 'idApp': '1,2,3'.

        -----------
        Returns: 
            response (dict): a dictionary with the response from the server
        '''
        
        encoded_params = urlencode(create_params, doseq=True).replace('%2C', ',')        
        response = self._send_request(method=self.METHOD_POST, url=f'{url}?{encoded_params}').json()
        
        nl = '\n'
        if response['code'] != 200:
            if response['code'] == 400:
                raise MyTrackerError(f'Bad request. {response["data"]["error"]["detail"]}.{nl}Response: {response}')
            elif response['code'] == 403:
                raise MyTrackerError(f'Access denied. Maybe you made mistakes or forgot to send authorization data.{nl}Response: {response}')
            else:
                raise MyTrackerError(f'Unknown error.{nl}Response: {response}')
        
        return response
    
    def get_export(self, get_params, url):
        ''' 
        Checking the status of the data export request. 

        -----------
        Parameters:
            get_params (dict): a dictionary with export ID parameter
            url (str): API endpoint to send request

        Example:
            First you need to get the export ID (create_export method)
        
            - Raw Data
            get_params = {
                'idRawExport': create_export_response['data']['idRawExport']
            }
            
            - Report
            get_params = {
                'idReportFile': create_export_response['data']['idReportFile']
            }
            
            - Segment
            get_params = {
                'idSegmentExport': create_export_response['data']['idSegmentExport']
            }
        
        -----------
        Returns: 
            response (dict): a dictionary with the response from the server
        '''
        
        encoded_params = urlencode(get_params)
        response = self._send_request(method=self.METHOD_GET, url=f'{url}?{encoded_params}').json()
        return response
        
    def get_raw_data(self, params, return_df=True):
        ''' 
        Uploading data via Raw Data API.
        
        -----------
        Parameters:
            params (dict): a dictionary with raw data export parameters (see on https://tracker.my.com/docs/api/export-api/raw/create)
            return_df (bool, default True): if True, then return a raw pd.DataFrame
                                            if False, then return a dictionary with the response from the server
            
        Example:
            params = {
                'dateFrom': '2022-05-01',
                'dateTo': '2022-05-31',
                'selectors': 'idAdEventTypeTitle,tsClick,tsView,dtEvent,tsEvent,idPartnerTitle,advertisingId',
                'idApp': 1,  
                'event': 'installs'
            }
            
            If you want to get data for multiple apps (accounts, etc.), 
            then add square brackets to the key 'idApp[]': [1, 2, 3],
            or specify the desired values in the string separated by commas 'idApp': '1,2,3'.
        -----------
        Returns: pd.DataFrame or dict
            raw_data (pd.DataFrame): raw dataframe
            or
            response (dict): a dictionary with the response from the server
        '''
        
        create_response = self.create_export(params, url=self.CREATE_RAW_DATA_URL)
        nl = '\n'
        
        get_params = {
            'idRawExport': create_response['data']['idRawExport'],
        }
        while True:
            
            try:
                get_response = self.get_export(get_params, url=self.GET_RAW_DATA_URL)
            except KeyboardInterrupt:
                self.cancel_raw_data_export(get_params['idRawExport'])
                raise MyTrackerError(f'The program was interrupted. The request was canceled.')
            
            if get_response['code'] == 200:
                if get_response['data']['status'] == 'Success!':
                    if return_df is True:
                        raw_data = []
                        for file in get_response['data']['files']:
                            link = file['link']
                            with urlopen(link, timeout=10) as f:
                                raw_file = pd.read_csv(f, compression='gzip')
                            raw_data.append(raw_file)
                        raw_data = pd.concat(raw_data, ignore_index=True)
                        break
                    elif return_df is False:
                        return dict(get_response)
                    else:
                        raise MyTrackerError('Parameter return_df must be True or False.')

                elif get_response['data']['status'] in ('In progress', 'Error occurred'):
                    try:
                        time.sleep(3)
                        continue
                    except KeyboardInterrupt:
                        self.cancel_raw_data_export(get_params['idRawExport'])
                        raise MyTrackerError(f'The program was interrupted. The request was canceled.')

                elif get_response['data']['status'] == 'User error occurred':
                    raise MyTrackerError(f'{get_response["data"]["errorMessage"]}.{nl}Response: {get_response}')
                    
                elif get_response['data']['status'] == 'Canceled by user':
                    raise MyTrackerError(f'The request was canceled.{nl}Response: {get_response}')
                    
            elif get_response['code'] == 404:
                raise MyTrackerError(f'The request is unavailable or could not be found.{nl}Response: {get_response}')
            
            elif get_response['code'] == 403:
                raise MyTrackerError(f'Access denied. Maybe you made mistakes or forgot to send authorization data.{nl}Response: {get_response}')
                
            else:
                raise MyTrackerError(f'Unknown error.{nl}Response: {get_response}')
            
        return raw_data
    
    def cancel_raw_data_export(self, id_raw_export):
        ''' 
        Cancel uploading raw data. 
        
        -----------
        Parameters:
            id_raw_export (int): unique raw export integer value
            
        -----------
        Returns:
            response (dict): a dictionary with the response from the server
        '''
        
        params = {
            'idRawExport': id_raw_export,
        }
        cancel_response = self.get_export(params, url=self.CANCEL_RAW_DATA_URL)
        return dict(cancel_response)
    
    def get_report(self, params, return_df=True):
        ''' 
        Uploading data via Report API.
        
        -----------
        Parameters:
            params (dict): a dictionary with report export parameters (see on https://tracker.my.com/docs/api/export-api/report/create)
            return_df (bool, default True): if True, then return a raw pd.DataFrame
                                            if False, then return a dictionary with the response from the server
            
        Example:
            params = {
                'settings[selectors]': 'date,idPartner,sumCampaignCost',
                'settings[filter][date][from]': '2022-06-01',
                'settings[filter][date][to]': '2022-06-10',
                'settings[filter][dimension][idApp][value]': 1,
                'settings[filter][dimension][idPartner][value][]': [10006, 10008],
                'settings[idCurrency]': 840,
                'settings[tz]': 'Europe/Moscow',
                'settings[precision]': 5,
                'settings[retIndent]': 3600,
            }
            
            If you want to get data for multiple apps (partners, etc.), 
            then add square brackets to the key 'settings[filter][dimension][idApp][value][]': [1, 2, 3],
            or specify the desired values in the string 
            separated by commas 'settings[filter][dimension][idApp][value]': '1,2,3'.
        -----------
        Returns: pd.DataFrame or dict
            report (pd.DataFrame): report dataframe
            or
            response (dict): a dictionary with the response from the server
        '''
        
        if 'fileType' in params.keys():
            params['fileType'] = 'csv'
        
        create_response = self.create_export(params, url=self.CREATE_REPORT_URL)
        nl = '\n'
        
        get_params = {
            'idReportFile': create_response['data']['idReportFile'],
        }

        while True:
            get_response = self.get_export(get_params, url=self.GET_REPORT_URL)
            
            if get_response['code'] == 200:
                if get_response['data']['status'] == 'Success!':
                    if return_df is True:
                        link = get_response['data']['files'][0]['link']
                        with urlopen(link, timeout=10) as file:
                            report = pd.read_csv(file, compression='gzip')
                        break
                    elif return_df is False:
                        return dict(get_response)
                    else:
                        raise MyTrackerError('Parameter return_df must be True or False.')

                elif get_response['data']['status'] == 'In progress':
                    time.sleep(3)
                    continue

                elif get_response['data']['status'] == 'Error occurred':
                    raise MyTrackerError(f'Error ocurred. The file will never be created.{nl}Response: {get_response}')
                    
            elif get_response['code'] == 404:
                raise MyTrackerError(f'The file is unavailable or could not be found.{nl}Response: {get_response}')
                
            elif get_response['code'] == 403:
                raise MyTrackerError(f'Access denied. Maybe you made mistakes or forgot to send authorization data.{nl}Response: {get_response}')

            else:
                raise MyTrackerError(f'Unknown error.{nl}Response: {get_response}')
        
        return report
    
    def get_segment(self, params):
        '''
        Uploading data via Segment API.
        
        -----------
        Parameters:
            params (dict): a dictionary with segment export parameters (see on https://tracker.my.com/docs/api/export-api/segment/export/create)
            
        Example:
            params = {
                'idSegment': 1111,
                'requestFields': 'idfa',
                'includeHeaderLine': 1,
                'registerType': 0,
                'hashType': 0
            }
            
            If you want to get data with multiple requestFields, 
            then add square brackets to the key 'requestFields[]': ['idfa', 'gaid'],
            or specify the desired values in the string
            separated by commas 'requestFields': 'idfa,gaid'.
        -----------
        Returns:
            response (dict): a dictionary with the response from the server
        '''
    
        create_response = self.create_export(params, url=self.CREATE_SEGMENT_URL)
        nl = '\n'
        
        get_params = {
            'idSegmentExport': create_response['data']['idSegmentExport'],
        }
        
        while True:
            get_response = self.get_export(get_params, url=self.GET_SEGMENT_URL)
            
            if get_response['code'] == 200:
                if get_response['data']['status'] == 'Success!':
                    break

                elif get_response['data']['status'] in ('In progress', 'Error occurred'):
                    time.sleep(3)
                    continue

            elif get_response['code'] == 404:
                raise MyTrackerError(f'The request is unavailable or could not be found.{nl}Response: {get_response}')
            
            elif get_response['code'] == 403:
                raise MyTrackerError(f'Access denied. Maybe you made mistakes or forgot to send authorization data.{nl}Response: {get_response}')
            
            else:
                raise MyTrackerError(f'Unknown error.{nl}Response: {get_response}')
        
        return dict(get_response)
