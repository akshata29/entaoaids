import os
import logging

try:
    OpenAiKey = os.environ['OpenAiKey']
    OpenAiVersion = os.environ['OpenAiVersion']
    OpenAiChat = os.environ['OpenAiChat']
    OpenAiEndPoint = os.environ['OpenAiEndPoint']
    OpenAiDocStorName = os.environ['OpenAiDocStorName']
    OpenAiDocStorKey = os.environ['OpenAiDocStorKey']
    OpenAiDocConnStr = f"DefaultEndpointsProtocol=https;AccountName={OpenAiDocStorName};AccountKey={OpenAiDocStorKey};EndpointSuffix=core.windows.net"
    OpenAiDocContainer = os.environ['OpenAiDocContainer']

    if "TenantId" in os.environ: 
        TenantId = os.environ['TenantId']
    else:
        TenantId = ""

    if "ClientId" in os.environ: 
        ClientId = os.environ['ClientId']
    else:
        ClientId = ""

    if "ClientSecret" in os.environ: 
        ClientSecret = os.environ['ClientSecret']
    else:
        ClientSecret = ""

    if "BlobAccountName" in os.environ: 
        BlobAccountName = os.environ['BlobAccountName']
    else:
        BlobAccountName = ""


    if "KbIndexName" in os.environ: 
        KbIndexName = os.environ['KbIndexName']
    else:
        KbIndexName = "aoaikb"
        
    if "SearchKey" in os.environ: 
        SearchKey = os.environ['SearchKey']
    else:
        SearchKey = ""

    if "SearchService" in os.environ: 
        SearchService = os.environ['SearchService']
    else:
        SearchService = ""

    if "BingUrl" in os.environ: 
        BingUrl = os.environ['BingUrl']
    else:
        BingUrl = ""

    if "BingKey" in os.environ: 
        BingKey = os.environ['BingKey']
    else:
        BingKey = ""

    if "CosmosEndpoint" in os.environ: 
        CosmosEndpoint = os.environ['CosmosEndpoint']
    else:
        CosmosEndpoint = ""

    if "CosmosKey" in os.environ: 
        CosmosKey = os.environ['CosmosKey']
    else:
        CosmosKey = ""
    
    if "CosmosDatabase" in os.environ: 
        CosmosDatabase = os.environ['CosmosDatabase']
    else:
        CosmosDatabase = ""

    if "CosmosContainer" in os.environ: 
        CosmosContainer = os.environ['CosmosContainer']
    else:
        CosmosContainer = ""

    if "OpenAiEmbedding" in os.environ: 
        OpenAiEmbedding = os.environ['OpenAiEmbedding']
    else:
        OpenAiEmbedding = "embedding"

    if "UploadPassword" in os.environ: 
        UploadPassword = os.environ['UploadPassword']
    else:
        UploadPassword = "P@ssw0rd"

    if "AdminPassword" in os.environ: 
        AdminPassword = os.environ['AdminPassword']
    else:
        AdminPassword = "P@ssw0rd"

    if "OpenAiApiKey" in os.environ: 
        OpenAiApiKey = os.environ['OpenAiApiKey']
    else:
        OpenAiApiKey = ""

    if "FormRecognizerKey" in os.environ: 
        FormRecognizerKey = os.environ['FormRecognizerKey']
    else:
        FormRecognizerKey = ""

    if "FormRecognizerEndPoint" in os.environ: 
        FormRecognizerEndPoint = os.environ['FormRecognizerEndPoint']
    else:
        FormRecognizerEndPoint = ""
    
    if "WeatherEndPoint" in os.environ: 
        WeatherEndPoint = os.getenv('WeatherEndPoint')
    else:
        WeatherEndPoint = ""
    
    if "WeatherHost" in os.environ: 
        WeatherHost = os.getenv('WeatherHost')
    else:
        WeatherHost = ""

    if "StockEndPoint" in os.environ: 
        StockEndPoint = os.getenv('StockEndPoint')
    else:
        StockEndPoint = ""
    
    if "StockHost" in os.environ: 
        StockHost = os.getenv('StockHost')
    else:
        StockHost = ""

    if "RapidApiKey" in os.environ: 
        RapidApiKey = os.getenv('RapidApiKey')
    else:
        RapidApiKey = ""

except Exception as e:
    logging.info("Error reading environment variables: %s",e)
