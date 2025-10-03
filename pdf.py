import pandas as pd
from urllib.parse import urlencode

def genEquipmentURLs(csv_df: pd.DataFrame):
    
    for idx, row in csv_df.iterrows():
        params = {
            "code": row['Code matériel'],
            "model": row['Modèle']
        }
        
        # query = "type=printer" + "&code=" + row['Code matériel'] + "&model=" + row['Modèle'] + "&serialNumber=" + row['Numéro de Série']
        encoded_query = urlencode(params, encoding='utf-8')
    
        url = "https://apps-hrc.adi.adies.lan/mailer/new-ticket?" + encoded_query
        print(url)
        
        break
        
