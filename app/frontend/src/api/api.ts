import { AskRequest, AskResponse, ChatResponse,  UserInfo} from "./models";
import { Any } from "@react-spring/web";

export async function getUserInfo(): Promise<UserInfo[]> {
  const response = await fetch('/.auth/me');
  if (!response.ok) {
      console.log("No identity provider found. Access to chat will be blocked.")
      return [];
  }

  const payload = await response.json();
  return payload;
}

export async function refreshIndex() : Promise<any> {
  
  const response = await fetch('/refreshIndex', {
    method: "GET",
    headers: {
        "Content-Type": "application/json"
    },
  });

  const result = await response.json();
  if (response.status > 299 || !response.ok) {
    return "Error";
  }
  return result;
}
export async function uploadFile(fileName:string, fileContent:any, contentType:string) : Promise<string> {
  
  const response = await fetch('/uploadFile', {
    method: "POST",
    headers: {
        "Content-Type": "application/json"
    },
    body: JSON.stringify({
      fileName:fileName,
      fileContent: fileContent,
      contentType:contentType
    })
  });

  const result = await response.json();
  if (response.status > 299 || !response.ok) {
    return "Error";
  }
  return "Success";
}
export async function uploadBinaryFile(formData:any, indexName:string) : Promise<string> {
  const response = await fetch('/uploadBinaryFile', {
    method: "POST",
    body: formData
  });

  const result = await response.json();
  if (response.status > 299 || !response.ok) {
    return "Error";
  }
  return "Success";
}
export async function uploadSummaryBinaryFile(formData:any) : Promise<string> {
  const response = await fetch('/uploadSummaryBinaryFile', {
    method: "POST",
    body: formData
  });

  const result = await response.json();
  if (response.status > 299 || !response.ok) {
    return "Error";
  }
 
  return "Success";
}
export async function processDoc(indexType: string, loadType : string, multiple: string, indexName : string, files: any,
  blobConnectionString : string, blobContainer : string, blobPrefix : string, blobName : string,
  s3Bucket : string, s3Key : string, s3AccessKey : string, s3SecretKey : string, s3Prefix : string,
  existingIndex : string, existingIndexNs: string, embeddingModelType: string,
  textSplitter:string, chunkSize:any, chunkOverlap:any, promptType:string, deploymentType:string) : Promise<string> {
  const response = await fetch('/processDoc', {
    method: "POST",
    headers: {
        "Content-Type": "application/json"
    },
    body: JSON.stringify({
      indexType:indexType,
      multiple: multiple,
      loadType:loadType,
      indexName:indexName,
      existingIndex:existingIndex,
      existingIndexNs:existingIndexNs,
      embeddingModelType:embeddingModelType,
      textSplitter:textSplitter,
      chunkSize:chunkSize,
      chunkOverlap:chunkOverlap,
      promptType:promptType,
      deploymentType:deploymentType,
      postBody: {
        values: [
          {
            recordId: 0,
            data: {
              text: files,
              blobConnectionString: blobConnectionString,
              blobContainer : blobContainer,
              blobPrefix : blobPrefix,
              blobName : blobName,
              s3Bucket: s3Bucket,
              s3Key : s3Key,
              s3AccessKey : s3AccessKey,
              s3SecretKey : s3SecretKey,
              s3Prefix : s3Prefix
            }
          }
        ]
      }
    })
  });

  const parsedResponse: ChatResponse = await response.json();
  if (response.status > 299 || !response.ok) {
      return "Error";
  } else {
    if (parsedResponse.values[0].data.error) {
      return parsedResponse.values[0].data.error;
    }
    return 'Success';
  }
  // if (response.status > 299 || !response.ok) {
  //   return "Error";
  // }
  
  // return "Success";
}
export async function processSummary(indexNs: string, indexType: string, existingSummary : string, fullDocumentSummary : boolean, options : AskRequest) : Promise<AskResponse> {
  const response = await fetch('/processSummary', {
    method: "POST",
    headers: {
        "Content-Type": "application/json"
    },
    body: JSON.stringify({
      indexNs:indexNs,
      indexType: indexType,
      existingSummary: existingSummary,
      fullDocumentSummary : fullDocumentSummary,
      postBody: {
        values: [
          {
            recordId: 0,
            data: {
              text: '',
              overrides: {
                  promptTemplate: options.overrides?.promptTemplate,
                  fileName: options.overrides?.fileName,
                  topics: options.overrides?.topics,
                  embeddingModelType: options.overrides?.embeddingModelType,
                  chainType: options.overrides?.chainType,
                  temperature: options.overrides?.temperature,
                  tokenLength: options.overrides?.tokenLength,
                  top: options.overrides?.top,
                  deploymentType: options.overrides?.deploymentType,
                }

            }
          }
        ]
      }
    })
  });
  const parsedResponse: ChatResponse = await response.json();
  if (response.status > 299 || !response.ok) {
      throw Error("Unknown error");
  }
  return parsedResponse.values[0].data
}
export async function verifyPassword(passType:string, password: string): Promise<string> {
  const response = await fetch('/verifyPassword' , {
      method: "POST",
      headers: {
          "Content-Type": "application/json"
      },
      body: JSON.stringify({
        passType:passType,
        password:password,
        postBody: {
          values: [
            {
              recordId: 0,
              data: {
                text: ''
              }
            }
          ]
        }
      })
  });

  const parsedResponse: ChatResponse = await response.json();
    if (response.status > 299 || !response.ok) {
        return "Error";
    } else {
      if (parsedResponse.values[0].data.error) {
        return parsedResponse.values[0].data.error;
      }
      return 'Success';
    }
}
export function getCitationFilePath(citation: string): string {
    return `/content/${citation}`;
}
