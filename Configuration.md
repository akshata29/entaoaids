# Configuration

## API Configuration

| Key | Default Value | Detail |
| --- | --- | ------------- |
|OpenAiKey||Your Azure OpenAI Key.  <br>You can get the OpenAI Key from Azure Portal for your deployed OpenAI service.
|OpenAiEndPoint||Fully qualified endpoint for Azure OpenAI <br>(https://<yourresource>.openai.azure.com/)
|OpenAiVersion|2023-05-15|API Version of the Azure OpenAI
|OpenAiEmbedding|text-embedding-ada-002|Deployment name of <br>text-embedding-ada-002 model in Azure OpenAI
|MaxTokens|500|Maximum Tokens
|Temperature|0.3|Temperature
|OpenAiChat|chat|Deployment name of gpt-35-turbo model in <br>Azure OpenAI
|OpenAiDocStorName||Document Storage account name
|OpenAiDocStorKey||Document Storage Key
|OpenAiDocContainer|chatpdf|Document storage container name
|SearchService||Azure Cognitive Search service name
|SearchKey||Azure Cognitive Search service Admin Key
|UploadPassword||Password required for upload functionality.
|AdminPassword||Password required for Admin capabilities.
|DOCGENERATOR_URL|Optional Settings|Required only if you are planning to use the AWS Integration.
|*PROMPTS*||Default Prompts for Speech Analytics Use-case. <br>26 Keys with different prompt.

## Application Configuration

| Key | Default Value | Detail |
| --- | --- | ------------- |
BLOB_CONTAINER_NAME||Blob container name where all PDF are uploaded
DOCGENERATOR_URL||Azure Function URL with host/default key <br> (https://<yourfunction>.azurewebsites.net/api/DocGenerator?code=<yourcode>)
SPEECH_KEY||Speech Service Key
SPEECH_REGION||Region where speech service is deployed <br> (i.e. eastus, southcentralus)
TEXTANALYTICS_KEY||Text Analytics(Language) Service Key
TEXTANALYTICS_REGION||Region where Text Analytics(Language) is deployed <br> (i.e. eastus, southcentralus)
VERIFYPASS_URL||Azure Function URL with host/default key <br> (https://<yourfunction>.azurewebsites.net/api/VerifyPassword?code=<yourcode>)
