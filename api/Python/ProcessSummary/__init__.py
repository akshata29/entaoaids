import logging, json, os
import azure.functions as func
import openai
import os
from langchain.chains.summarize import load_summarize_chain
from langchain.prompts import PromptTemplate
from typing import List
from Utilities.envVars import *
#from langchain.document_loaders import JSONLoader
from langchain_openai import AzureChatOpenAI
from langchain_openai import ChatOpenAI
from Utilities.cogSearch import findSummaryInIndex, performCogSearch, mergeDocs, createProspectusSummary, findTopicSummaryInIndex, performFullCogSearch
from langchain.docstore.document import Document
import uuid
from langchain_openai import OpenAIEmbeddings
from langchain_openai import AzureOpenAIEmbeddings
from langchain.chains.llm import LLMChain
from langchain.prompts import PromptTemplate
from langchain.chains.combine_documents.stuff import StuffDocumentsChain
from langchain.chains.mapreduce import MapReduceChain
from langchain.text_splitter import CharacterTextSplitter
from langchain.chains import ReduceDocumentsChain, MapReduceDocumentsChain
import time, re
from openai import OpenAI, AzureOpenAI, AsyncAzureOpenAI
from queue import Queue
from threading import Thread

# Example count_tokens function (if you have your own, use it)
def count_tokens(text):
    return len(text.split())

def get_chunks(full_text, OVERLAP=True, DEBUG=False):
    '''
    This will take a text and return an array with sliced chunks of the text in optimal sizing for summarization.  Note that by default, this does include overlaping text in each chunk.
    Overlaping allows more cohesion between text, and should only be turned off when trying to count specific numbers and no duplicated text is a requirment.
    
    We could just drop text up to the maximum context window of our model, but that actually doesn't work very well.
    Part of the reason for this is because no matter the input length, the output length is about the same.
    For example, if you drop in a paragraph or 10 pages, you get about a paragraph in response.
    To mitigate this, we create chunks using the lesser of two values: 25% of the total token count or 2k tokens.
    We'll also overlap our chunks by about a paragraph of text or so, in order to provide continuity between chunks.
    (Logic taken from https://gist.github.com/Donavan/4fdb489a467efdc1faac0077a151407a)
    '''
    DEBUG = False #debugging at this level is usually not very helpful.
    
    #Following testing, it was found that chunks should be 2000 tokens, or 25% of the doc, whichever is shorter.
    #max chunk size in tokens
    chunk_length_tokens = 2000
    #chunk length may be shortened later for shorter docs.
    
    #a paragraph is about 200 words, which is about 260 tokens on average
    #we'll overlap our chunks by a paragraph to provide cohesion to the final summaries.
    overlap_tokens = 260
    if not OVERLAP: overlap_tokens = 0
    
    #anything this short doesn't need to be chunked further.
    min_chunk_length = 260 + overlap_tokens*2
    
    
    #grab basic info about the text to be chunked.
    char_count = len(full_text)
    word_count = len(full_text.split(" "))#rough estimate
    token_count = count_tokens(full_text)
    token_per_charater = token_count/char_count

    
    #don't chunk tiny texts
    if token_count <= min_chunk_length:
        if DEBUG: logging.info("Text is too small to be chunked further")
        return [full_text]
        
    #if the text is shorter, use smaller chunks
    if (token_count/4<chunk_length_tokens):
        overlap_tokens = int((overlap_tokens/chunk_length_tokens)*int(token_count/4))
        chunk_length_tokens = int(token_count/4)
        
    #convert to charaters for easy slicing using our approximate tokens per character for this text.
    overlap_chars = int(overlap_tokens/token_per_charater)
    chunk_length_chars = int(chunk_length_tokens/token_per_charater)
    
    #itterate and create the chunks from the full text.
    chunks = []
    start_chunk = 0
    end_chunk = chunk_length_chars + overlap_chars
    
    last_chunk = False
    while not last_chunk:
        #the last chunk may not be the full length.
        if(end_chunk>=char_count):
            end_chunk=char_count
            last_chunk=True
        chunks.append(full_text[start_chunk:end_chunk])
        
        #move our slice location
        if start_chunk == 0:
            start_chunk += chunk_length_chars - overlap_chars
        else:
            start_chunk += chunk_length_chars
        
        end_chunk = start_chunk + chunk_length_chars + 2 * overlap_chars
        
    return chunks

def ask_azure_openai(client, prompt_text, DEBUG=False):
    '''
    Send a prompt to Azure OpenAI, and return the response.
    DEBUG is used to see exactly what is being sent to and from Azure OpenAI.
    '''

    # Ensure the prompt contains the expected format
    if "Assistant:" not in prompt_text:
        prompt_text = "\n\nHuman:" + prompt_text + "\nAssistant: "

    # Prompt payload for Azure OpenAI
    prompt_json = {
        "prompt": prompt_text,
        "max_tokens": 3000,
        "temperature": 0.7,
        "top_p": 0.7,
        "frequency_penalty": 0,
        "presence_penalty": 0,
        "stop": ["\n\nHuman:"]
    }
    
    # Cache results if present
    body = json.dumps(prompt_json)

    start_time = time.time()
    attempt = 1
    MAX_ATTEMPTS = 3
    while True:
        try:
            query_start_time = time.time()

            messages=[
                {"role": "system", "content": prompt_text}]

            # Invoke the Azure OpenAI model
            response = client.chat.completions.create(
                messages=messages,
                temperature=0,
                max_tokens=3500,
                model=OpenAiChat,
            )
            
            # Extract the result from the response
            raw_results = response.choices[0].message.content.strip(" \n")

            # Remove any unwanted HTML-like tags if they appear
            results = re.sub('<[^<]+?>', '', raw_results)

            # Compute metrics
            request_time = round(time.time() - start_time, 2)
            if DEBUG:
                logging.info("Received:", results)
                logging.info("request time (sec):", request_time)

            total_tokens = count_tokens(prompt_text + raw_results)  # Assuming you have a count_tokens function
            output_tokens = count_tokens(raw_results)
            tokens_per_sec = round(total_tokens / request_time, 2)
            break

        except Exception as e:
            logging.info(f"Error with Azure OpenAI API call: {str(e)}")
            attempt += 1
            if attempt > MAX_ATTEMPTS:
                logging.info("Max attempts reached!")
                results = str(e)
                request_time = -1
                total_tokens = -1
                output_tokens = -1
                tokens_per_sec = -1
                break
            else:
                # Retry after 10 seconds
                time.sleep(10)

    return (prompt_text, results, total_tokens, output_tokens, request_time, tokens_per_sec, query_start_time)

# Threaded function for queue processing.
def thread_request(client, q, result):
    while not q.empty():
        work = q.get()                      #fetch new work from the Queue
        thread_start_time = time.time()
        try:
            data = ask_azure_openai(client, work[1])
            result[work[0]] = data          #Store data back at correct index
        except Exception as e:
            error_time = time.time()
            logging.info('Error with prompt!',str(e))
            result[work[0]] = (work[1],str(e),count_tokens(work[1]),0,round(error_time-thread_start_time,2),0,thread_start_time)
        #signal to the queue that task has been processed
        q.task_done()
    return True

def ask_aoai_threaded(client, prompts,DEBUG=False):
    '''
    Call ask_azure_openai, but multi-threaded.
    Returns a dict of the prompts and responces.
    '''
    q = Queue(maxsize=0)
    num_theads = min(50, len(prompts))
    
    #Populating Queue with tasks
    results = [{} for x in prompts];
    #load up the queue with the promts to fetch and the index for each job (as a tuple):
    for i in range(len(prompts)):
        #need the index and the url in each queue item.
        q.put((i,prompts[i]))
        
    #Starting worker threads on queue processing
    for i in range(num_theads):
        #logging.info('Starting thread ', i)
        worker = Thread(target=thread_request, args=(client, q,results))
        worker.setDaemon(True)    #setting threads as "daemon" allows main program to 
                                  #exit eventually even if these dont finish 
                                  #correctly.
        worker.start()

    #now we wait until the queue has been processed
    q.join()

    if DEBUG:logging.info('All tasks completed.')
    return results

def get_prompt(text,prompt_type,format_type, manual_guidance, style_guide, docs_description=""):
    '''
    text should be a single string of the raw text to be sent to the gen ai model.
    prompt_type must be "summary" or "interrogate" or "answers"
            -summary means summarize the text
            -interrogate means look at the text and ask questions about what is missing
            -answers means looking at the test, provide only details that may help answer the questions according to the Guidance.
            -merge_answers takes a summary as text, and merges in the facts in the guidance section
            -merge_summaries takes 2 or more summaries and merges them together.  The summaries to be merged must be in list format for best results.
            -reporter - like a new reporter, extract details that help answer the guidance questions
            -reporter_summary - like a news reporter looking at a bunch of notes, create a list summary.  Intended as an intermediate step. 
            reporter_final - generative a narrative based on the reporter_summary outputs.
    format_type must be "narrative" or "list"
    manual_guidance Extra instructions to guide the process, usually from the user.
    style_guide TBD
    
    Note that merge_summaries is handled differntly than all other options because it iteratively adds in multiple texts.
    '''
    
    prompt_template = """\n\nHuman:  I am going to give you a text{{GUIDANCE_1}}.  This text is extracted from a larger document.  Here is the text:

    <text>
    {{TEXT}}
    </text>
    {{GUIDANCE_2}}
    {{STYLE}}{{REQUEST}}{{FORMAT}}{{GUIDANCE_3}}
    \nAssistant:  Here is what you asked for:
    """

    merge_prompt_template = """\n\nHuman:  Here are a number of related summaries:

    {{TEXT}}
    Please merge these summaries into a highly detailed single summary in {{FORMAT}} format, preserving as much detail as possible, using less than 1000 tokens.
    \nAssistant:  Here is what you asked for:
    """

    #this is inserted into the prompt template above, in the {{GUIDANCE_2}} section.
    guidance_tempate = """
    Here is the additional guidance:
    <guidance>
    {{GUIDANCE}}
    </guidance>
    """

    #this prompt asks the LLM to be a newpaper reporter, extracting facts from a document to be used in a later report.  Good for summarizing factual sets of documents.
    reporter_prompt = """\n\nHuman:  You are a newspaper reporter, collecting facts to be used in writing an article later.  Consider this source text:
    <text>
    {{TEXT}}
    </text>
    {{DOCS_DESCRIPTION}}  Please create a {{FORMAT}} of all the relevant facts from this text which will be useful in answering the question "{{GUIDANCE}}".  To make your list as clear as possible, do not use and pronouns or ambigious phrases.  For example, use a company's name rather than saying "the company" or they.
    \nAssistant:  Here is the {{FORMAT}} of relevant facts:
    """

    reporter_summary_prompt = """\n\nHuman:  You are a newspaper reporter, collecting facts to be used in writing an article later.  Consider these notes, each one derived from a different source text:
    {{TEXT}}
    Please create a {{FORMAT}} of all the relevant facts and trends from these notes which will be useful in answering the question "{{GUIDANCE}}"{{STYLE}}.  To make your list as clear as possible, do not use and pronouns or ambigious phrases.  For example, use a company's name rather than saying "the company" or "they".
    \nAssistant:  Here is the list of relevant facts:

    """

    reporter_final_prompt = """\n\nHuman:  You are a newspaper reporter, writing an article based on facts that were collected and summarized earlier.  Consider these summaries:
    {{TEXT}}
    Each summary is a collection of facts extracted from a number of source reports.  Each source report was written by an AWS team talking about their interactions with their individual customer.  Please create a {{FORMAT}} of all the relevant trends and details from these summaries which will be useful in answering the question "{{GUIDANCE}}".
    \nAssistant:  Here is the narrative:


    """
    #answers mode is a bit different, so handle that first.
    if prompt_type == "answers":
        format_type = "in list format, using less than 1000 tokens.  "
        prompt_type = "Please provide a list of any facts from the text that could be relevant to answering the questions from the guidance section "
        guidance_1 = " and some guidance"
        guidance_2 = guidance_tempate.replace("{{GUIDANCE}}",manual_guidance)
        guidance_3 = "You should ignore any questions that can not be answered by this text."
    elif prompt_type == "reporter":
        return reporter_prompt.replace("{{TEXT}}",text).replace("{{FORMAT}}",format_type).replace("{{GUIDANCE}}",manual_guidance).replace("{{DOCS_DESCRIPTION}}",docs_description)
    elif prompt_type == "reporter_summary":
        summaries_text = ""
        for x,summary in enumerate(text):
            summaries_text += "<note_%s>\n%s</note_%s>\n"%(x+1,summary,x+1)
        final_prompt = reporter_summary_prompt.replace("{{TEXT}}",summaries_text).replace("{{FORMAT}}",format_type).replace("{{GUIDANCE}}",manual_guidance).replace("{{STYLE}}",style_guide)
        return final_prompt
    elif prompt_type == "reporter_final":
        summaries_text = ""
        for x,summary in enumerate(text):
            summaries_text += "<summary_%s>\n%s</summary_%s>\n"%(x+1,summary,x+1)
        final_prompt = reporter_final_prompt.replace("{{TEXT}}",summaries_text).replace("{{FORMAT}}",format_type).replace("{{GUIDANCE}}",manual_guidance)
        return final_prompt
    elif prompt_type == "merge_summaries":
        summaries_text = ""
        for x,summary in enumerate(text):
            summaries_text += "<summary_%s>\n%s</summary_%s>\n"%(x+1,summary,x+1)
        final_prompt = merge_prompt_template.replace("{{TEXT}}",summaries_text).replace("{{FORMAT}}",format_type)
        return final_prompt
        
    elif prompt_type == "merge_answers":
        prompt_type = "The text is a good summary which may lack a few details.  However, the additional information found in the guidance section can be used to make the summary even better.  Starting with the text, please use the details in the guidance section to make the text more detailed.  The new summary shoud use less than 1000 tokens.  "
        format_type = ""
        guidance_1 = " and some guidance"
        guidance_2 = guidance_tempate.replace("{{GUIDANCE}}",manual_guidance)
        guidance_3 = "You should ignore any comments in the guidance section indicating that answers could not be found."
    else:
        #Based on the options passed in, grab the correct text to eventually use to build the prompt.
        #select the correct type of output format desired, list or summary.  Note that list for interrogate prompts is empty because the request for list is built into that prompt.
        if prompt_type == "interrogate" and format_type != "list":
            raise ValueError("Only list format is supported for interrogate prompts.")
        if format_type == "list":
            if prompt_type == "interrogate":
                format_type = ""#already in the prompt so no format needed.
            else:
                format_type = "in list format, using less than 1000 tokens."
        elif format_type == "narrative":
            format_type = "in narrative format, using less than 1000 tokens."
        else:
            raise ValueError("format_type must be 'narrative' or 'list'.")

        #select the correct prompt type language
        if prompt_type == "summary":
            prompt_type = "Please provide a highly detailed summary of this text "
        elif prompt_type == "interrogate":
            prompt_type = "This text is a summary that lacks detail.  Please provide a list of the top 10 most important questions about this text that can not be answered by the text."
        else:
            raise ValueError("prompt_type must be 'summary' or 'interrogate'.")

        if manual_guidance == "":
            guidance_1 = ""
            guidance_2 = ""
            guidance_3 = ""
        else:
            guidance_1 = " and some guidance"
            guidance_2 = guidance_tempate.replace("{{GUIDANCE}}",manual_guidance)
            guidance_3 = "  As much as possible, also follow the guidance from the guidance section above.  You should ignore guidance that does not seem relevant to this text."
        
    #TBD
    style_guide = ""
    #logging.info (prompt_template.replace("{{GUIDANCE_1}}",guidance_1).replace("{{GUIDANCE_2}}",guidance_2).replace("{{GUIDANCE_3}}",guidance_3).replace("{{STYLE}}",style_guide).replace("{{REQUEST}}",prompt_type).replace("{{FORMAT}}",format_type))
    final_prompt = prompt_template.replace("{{TEXT}}",text).replace("{{GUIDANCE_1}}",guidance_1).replace("{{GUIDANCE_2}}",guidance_2).replace("{{GUIDANCE_3}}",guidance_3).replace("{{STYLE}}",style_guide).replace("{{REQUEST}}",prompt_type).replace("{{FORMAT}}",format_type)
    return final_prompt

def generate_summary_from_chunks(client, chunks, prompt_options,DEBUG=False, chunks_already_summarized=False):
    """
    This function itterates through a list of chunks, summarizes them, then merges those summaries together into one.
    chunks_already_summarized is used when the chunks passed in are chunks resulting from summerizing docs.
    If the chunks are taken from a source document directly, chunks_already_summarized should be set to False.
    """
    partial_summaries = {}
    if not chunks_already_summarized:#chunks are from a source doc, so summarize them.
        partial_summaries_prompts = []
        partial_summaries_prompt2chunk = {}
        for x,chunk in enumerate(chunks):
            #if DEBUG: logging.info ("Working on chunk",x+1,end = '')
            start_chunk_time = time.time()
            #note that partial summaries are always done in list format to maximize information captured.
            custom_prompt = get_prompt(chunk,prompt_options['prompt_type'],'list', prompt_options['manual_guidance'], prompt_options['style_guide'])
            #partial_summaries[chunk] = ask_claude(custom_prompt,DEBUG=False)
            partial_summaries_prompts.append(custom_prompt)
            partial_summaries_prompt2chunk[custom_prompt]=chunk
        
        partial_summaries_results = ask_aoai_threaded(client, partial_summaries_prompts)
        for prompt_text,results,total_tokens,output_tokens,request_time,tokens_per_sec,query_start_time in partial_summaries_results:
            partial_summaries[partial_summaries_prompt2chunk[prompt_text]] = results

        if DEBUG: 
            logging.info ("Partial summary chunks done!")
            logging.info ("Creating joint summary...")
    else:
        for chunk in chunks:
            partial_summaries[chunk] = chunk
        if DEBUG: 
            logging.info ("Summarized chunks detected!")
            logging.info ("Creating joint summary...")
            
    summaries_list = []
    summaries_list_token_count = 0
    for chunk in chunks:
        summaries_list.append(partial_summaries[chunk]) 
        summaries_list_token_count+=count_tokens(partial_summaries[chunk])
        
    if DEBUG: logging.info("Chunk summaries token count:",summaries_list_token_count)
    
    #check to see if the joint summary is too long.  If it is, recursivly itterate down.
    #we do this, rather than chunking again, so that summaries are not split.
    #it needs to be under 3000 tokens in order to be helpful to the summary (4000 is an expiremental number and may need to be adjusted.)
    #this may be higher than the 2000 used for text originally, because this data is in list format.
    recombine_token_target = 3000
    #summaries_list_token_count = recombine_token_target+1 #set this to target+1 so that we do at least one recombonation for shorter documents.
    while summaries_list_token_count>recombine_token_target:
        if DEBUG: logging.info("Starting reduction loop to merge chunks.  Total token count is %s"%summaries_list_token_count)
        new_summaries_list = []
        summaries_list_token_count = 0
        temp_summary_group = []
        temp_summary_group_token_length = 0
        for summary in summaries_list:
            if temp_summary_group_token_length + count_tokens(summary) > recombine_token_target:
                #the next summary added would push us over the edge, so summarize the current list, and then add it.
                #note that partial summaries are always done in list format to maximize information captured.
                if DEBUG: logging.info("Reducing %s partial summaries into one..."%(len(temp_summary_group)))
                custom_prompt = get_prompt(temp_summary_group,"merge_summaries","list", prompt_options['manual_guidance'], prompt_options['style_guide'])
                temp_summary = ask_azure_openai(client, custom_prompt,DEBUG=False)[1]
                new_summaries_list.append(temp_summary)
                summaries_list_token_count+= count_tokens(temp_summary)
                temp_summary_group = []
                temp_summary_group_token_length = 0
            
            temp_summary_group.append(summary)
            temp_summary_group_token_length+= count_tokens(summary)
        
        #summarize whever extra summaries are still in the temp list
        if len(temp_summary_group)>1:
            if DEBUG: logging.info("Starting final reduction of %s partial summaries into one..."%(len(temp_summary_group)))
            custom_prompt = get_prompt(temp_summary_group,"merge_summaries","list", prompt_options['manual_guidance'], prompt_options['style_guide'])
            temp_summary = ask_azure_openai(client, custom_prompt,DEBUG=False)[1]
            new_summaries_list.append(temp_summary)
            summaries_list_token_count+= count_tokens(temp_summary)
        elif len(temp_summary_group)==1:
            if DEBUG: logging.info("Tacking on an extra partial summary")
            new_summaries_list.append(temp_summary_group[0])
            summaries_list_token_count+= count_tokens(temp_summary_group[0])
            
        summaries_list = new_summaries_list
        
    if DEBUG: logging.info ("Final merge of summary chunks, merging %s summaries."%(len(summaries_list)))
    custom_prompt = get_prompt(summaries_list,"merge_summaries",prompt_options['format_type'], prompt_options['manual_guidance'], prompt_options['style_guide'])
    full_summary = ask_azure_openai(client, custom_prompt,DEBUG=False)[1]
    #full_summary_prompt = get_prompt("/n".join(summaries_list),prompt_options['prompt_type'],prompt_options['format_type'], prompt_options['manual_guidance'], prompt_options['style_guide'])
    #full_summary = ask_claude(full_summary_prompt,DEBUG=False)
    
    return full_summary

def generate_single_doc_summary(client, full_text, prompt_options,AUTO_REFINE=True, DEBUG=False,ALREADY_CHUNKED_AND_SUMMED=False):
    """
    This function uses the three helper functions, as well as the generate_summary_from_chunks above, to iteratively generate high quality summaries.
    AUTO_REFINE, if true, has the LLM generate a list of questions, and then recursivly calls this function with those questions for guidance.
    ALREADY_CHUNKED_AND_SUMMED, if true, means that this is being called using a list of summarized documents which should not be chunked or summarized further.
    """
    #first break this document into chunks
    chunks = []        
    
    if ALREADY_CHUNKED_AND_SUMMED:
        chunks = full_text
    else:
        chunks = get_chunks(full_text,DEBUG=DEBUG)
        
    if DEBUG:
        if prompt_options['prompt_type'] == "answers":
            logging.info ("Generating answers using %s chunks."%(len(chunks)))
        else:
            logging.info ("Generating a new combined summary for %s chunks."%(len(chunks)))
        if ALREADY_CHUNKED_AND_SUMMED:
            logging.info ("Input has already been chunked and summarized, skipping initial chunking.")
        
            
    first_summary = generate_summary_from_chunks(client, chunks,prompt_options,DEBUG=DEBUG, chunks_already_summarized=ALREADY_CHUNKED_AND_SUMMED)
    
    if DEBUG and AUTO_REFINE: 
        logging.info ("First summary:")
        logging.info (first_summary)
        
    if AUTO_REFINE: 
        if DEBUG: logging.info ("Asking the LLM to find weaknesses in this summary...")
        #now that we have a rough summary, let's grab some questions about it.
        questions_prompt = get_prompt(first_summary,"interrogate","list", "", "")
        questions_list = ask_azure_openai(client, questions_prompt,DEBUG=False)[1]

        if DEBUG: 
            logging.info ("Questions from the LLM:")
            logging.info (questions_list)
            
        original_guidance = prompt_options['manual_guidance']
        original_prompt_type = prompt_options['prompt_type']
        prompt_options['manual_guidance'] = prompt_options['manual_guidance'] + questions_list
        prompt_options['prompt_type'] = "answers"
        add_details = generate_single_doc_summary(full_text, prompt_options,AUTO_REFINE=False, DEBUG=DEBUG, ALREADY_CHUNKED_AND_SUMMED=ALREADY_CHUNKED_AND_SUMMED)
        if DEBUG: 
            logging.info("Additional Details:")
            logging.info (add_details)
            logging.info("Merging details into original summary...")
        
        prompt_options['manual_guidance'] = original_guidance + add_details
        prompt_options['prompt_type'] = "merge_answers"
        custom_prompt = get_prompt(first_summary,prompt_options['prompt_type'],prompt_options['format_type'], prompt_options['manual_guidance'], prompt_options['style_guide'])
        final_summary = ask_azure_openai(client, custom_prompt,DEBUG=False)[1]
        
        #return this back to the original to prevent weird errors between calls of this function.
        prompt_options['manual_guidance'] = original_guidance
        prompt_options['prompt_type'] = original_prompt_type
        return final_summary
    
    else:
        return first_summary

def grab_set_chunks(lst, n):
    """Yield successive n-sized chunks from lst.
    This is a helper function for the multidoc summarization function.
    """
    for i in range(0, len(lst), n):
        yield lst[i:i + n]

def generate_multiple_docs_summary(client, docs, questions, docs_description, DEBUG=False):
    """
    This function uses the three helper functions to read the documents passed in, and create a summary answer for each question passed in.
    If the documents are longer than two pages or so, it is reccoemended that you first summaize each document.
    docs_description is a single sentance describing what the documents are such as "The texts are a collection of product reviews for a Pickle Ball paddle."
    """
    #get answers from each doc for each question.
    answers = {}
    prompt2quetion_doc = {}
    prompts = []
    max_docs_to_scan = 500
    
    #build the queries to be passed into Bedrock
    for question in questions:
        for x,doc in enumerate(docs):
            if x>max_docs_to_scan:break#limit for testing
            
            #logging.info ("Asking the LLM to find extract answers from this doc:",doc)
            questions_prompt = get_prompt(docs[doc],"reporter","list", question, "",docs_description)
            prompt2quetion_doc[questions_prompt] = (question,doc) 
            prompts.append(questions_prompt)
        
    if DEBUG:logging.info("Starting %s worker threads."%len(prompts))
    prompts_answers = ask_aoai_threaded(client, prompts,DEBUG=False)
    
    for question in questions:
        answers[question] = []    
    
    for prompt,answer,total_tokens,output_tokens,request_time,tokens_per_sec,query_start_time in prompts_answers:
        question,doc = prompt2quetion_doc[prompt]
        answers[question].append(answer)
        
    
    current_answer_count = len(docs)
    if DEBUG: logging.info("All documents have been read.  Reducing answers into the final summary...")
    #reduce this down to 5 or less docs for the final summary by combining the individual answers.
    while current_answer_count > 5:
        #summarize the answers
        prompts = []
        prompts2question = {}
        
        max_docs_to_scan = max(min(current_answer_count,8),3)
        if DEBUG: logging.info("Combining %s chunks.  (Currently there are %s answers to each question.)"%(max_docs_to_scan,current_answer_count))
        for question in questions:
            #logging.info ("Asking the LLM to summarize answers for this question:",question)
            #You want chunks of roughly 2K tokens
            for partial_chunks in grab_set_chunks(answers[question],max_docs_to_scan):
                questions_prompt = get_prompt(partial_chunks,"reporter_summary","list", question, " in less than 1000 tokens")
                prompts.append(questions_prompt)
                prompts2question[questions_prompt] = question
        
        if DEBUG:logging.info("Starting %s worker threads."%len(prompts))
        prompts_answers = ask_aoai_threaded(client, prompts,DEBUG=False)
        
        for question in questions:
            answers[question] = []    
        for prompt,answer,total_tokens,output_tokens,request_time,tokens_per_sec,query_start_time in prompts_answers:
            answers[prompts2question[prompt]].append(answer)        

        current_answer_count = len(answers[questions[0]])
        
    if DEBUG: logging.info("Creating the final summary for each question.")
    #write the final article:
    prompts = []
    prompts2question = {}
    for question in questions:
        #logging.info ("Asking the LLM to finalize the answer for this question:",question)
        questions_prompt = get_prompt(answers[question],"reporter_final","narrative", question, "")
        prompts.append(questions_prompt)
        prompts2question[questions_prompt] = question

    if DEBUG:logging.info("Starting %s worker threads."%len(prompts))
    prompts_answers = ask_aoai_threaded(client, prompts,DEBUG=False)
    
    answers = {}
    for prompt,answer,total_tokens,output_tokens,request_time,tokens_per_sec,query_start_time in prompts_answers:
        answers[prompts2question[prompt]] = answer
    return answers

def GetAllFiles(filesToProcess):
    files = []
    convertedFiles = {}
    for file in filesToProcess:
        files.append({
            "filename" : file['path'],
            "converted": False,
            "embedded": False,
            "converted_path": ""
            })
    logging.info(f"Found {len(files)} files in the container")
    for file in files:
        convertedFileName = f"converted/{file['filename']}.zip"
        if convertedFileName in convertedFiles:
            file['converted'] = True
            file['converted_path'] = convertedFiles[convertedFileName]

    logging.info(files)
    return files
    #return []

def main(req: func.HttpRequest, context: func.Context) -> func.HttpResponse:
    logging.info(f'{context.function_name} HTTP trigger function processed a request.')
    if hasattr(context, 'retry_context'):
        logging.info(f'Current retry count: {context.retry_context.retry_count}')

        if context.retry_context.retry_count == context.retry_context.max_retry_count:
            logging.info(
                f"Max retries of {context.retry_context.max_retry_count} for "
                f"function {context.function_name} has been reached")

    try:
        indexNs = req.params.get('indexNs')
        indexType = req.params.get('indexType')
        existingSummary = req.params.get('existingSummary')
        fullDocumentSummary = req.params.get('fullDocumentSummary')
        logging.info(f'indexNs: {indexNs}')
        logging.info(f'indexType: {indexType}')
        body = json.dumps(req.get_json())
    except ValueError:
        return func.HttpResponse(
             "Invalid body",
             status_code=400
        )

    if body:
        result = ComposeResponse(indexNs, indexType, existingSummary, fullDocumentSummary, body)
        return func.HttpResponse(result, mimetype="application/json")
    else:
        return func.HttpResponse(
             "Invalid body",
             status_code=400
        )

def ComposeResponse(indexNs, indexType, existingSummary, fullDocumentSummary, jsonData):
    values = json.loads(jsonData)['values']

    logging.info("Calling Compose Response")
    # Prepare the Output before the loop
    results = {}
    results["values"] = []

    for value in values:
        outputRecord = TransformValue(indexNs, indexType, existingSummary, fullDocumentSummary, value)
        if outputRecord != None:
            results["values"].append(outputRecord)
    return json.dumps(results, ensure_ascii=False)

def map_reduce_summary(llm,doc):
    # Map
    map_template = """\n\nHuman: The following is a set of documents
    <documnets>
    {docs}
    </documents>
    Based on this list of docs, please identify the main themes.

    Assistant:  Here are the main themes:"""
    map_prompt = PromptTemplate.from_template(map_template)
    map_chain = LLMChain(llm=llm, prompt=map_prompt)

    # Reduce
    reduce_template = """\n\nHuman: The following is set of summaries:
    <summaries>
    {doc_summaries}
    </summaries>
    Please take these and distill them into a final, consolidated summary of the main themes in narative format. 

    Assistant:  Here are the main themes:"""
    reduce_prompt = PromptTemplate.from_template(reduce_template)
    reduce_chain = LLMChain(llm=llm, prompt=reduce_prompt)

    # Takes a list of documents, combines them into a single string, and passes this to an LLMChain
    combine_documents_chain = StuffDocumentsChain(
        llm_chain=reduce_chain, document_variable_name="doc_summaries"
    )

    # Combines and iteravely reduces the mapped documents
    reduce_documents_chain = ReduceDocumentsChain(
        # This is final chain that is called.
        combine_documents_chain=combine_documents_chain,
        # If documents exceed context for `StuffDocumentsChain`
        collapse_documents_chain=combine_documents_chain,
        # The maximum number of tokens to group documents into.
        token_max=4000,
    )

    # Combining documents by mapping a chain over them, then combining results
    map_reduce_chain = MapReduceDocumentsChain(
        # Map chain
        llm_chain=map_chain,
        # Reduce chain
        reduce_documents_chain=reduce_documents_chain,
        # The variable name in the llm_chain to put the documents in
        document_variable_name="docs",
        # Return the results of the map steps in the output
        return_intermediate_steps=False,
    )

    if type(doc) == str:
        #use the LangChain built in text splitter to split our text
        from langchain.text_splitter import RecursiveCharacterTextSplitter
        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size = 5000,
            chunk_overlap  = 200,
            length_function = len,
            add_start_index = True,
        )
        split_docs = text_splitter.create_documents([doc])
    return map_reduce_chain.run(split_docs)

#wrapping in a python function to make it easy to use in other scripts.
def stuff_it_summary(llm, doc):
    # Define prompt
    prompt_template = """\n\nHuman:  Consider this text:
    <text>
    {text}
    </text>
    Please create a concise summary in narative format.

    Assistiant:  Here is the concise summary:"""
    prompt = PromptTemplate.from_template(prompt_template)

    # Define LLM chain
    llm_chain = LLMChain(llm=llm, prompt=prompt)

    # Define StuffDocumentsChain
    stuff_chain = StuffDocumentsChain(llm_chain=llm_chain, document_variable_name="text")

    #Note that although langchain often stores douments in small chunks for the 
    #convience of models with smaller context windows, this "stuff it" method will
    #combind all those chunks into a single prompt call.

    if type(doc) == str:
        docs = [Document(page_content=doc)]
    return stuff_chain.run(docs)

def summarizeTopic(llm, client, query, embeddingModelType, indexNs, indexType, topK):
    if indexType == 'cogsearchvs':
        try:
            if query == "FullDocument":
                r = performFullCogSearch(indexNs)          
                if r == None:
                    docContent = "No results found"
                else :
                    docContent = ' '.join([doc['content'] for doc in r])
            else:
                r = performCogSearch(indexType, embeddingModelType, query, indexNs, topK, returnFields=["id", "content", "metadata"] )          
                # if r == None:
                #     resultsDoc = [Document(page_content="No results found")]
                # else :
                #     resultsDoc = [
                #             Document(page_content=doc['content'], metadata={"id": doc['id']})
                #             for doc in r
                #             ]
                # logging.info(f"Found {len(resultsDoc)} Cog Search results")
                if r == None:
                    docContent = "No results found"
                else :
                    docContent = ' '.join([doc['content'] for doc in r])
        
            if len(docContent) == 0:
                return "I don't know"
            else:
                #stuffSummary = stuff_it_summary(llm, docContent)
                #return stuffSummary
                prompt_options = {}
                prompt_options['prompt_type'] = "summary"
                prompt_options['format_type'] = "narrative"
                prompt_options['manual_guidance'] = ""
                prompt_options['style_guide'] = ""

                revised_summary = generate_single_doc_summary(client, docContent, prompt_options, AUTO_REFINE=False, DEBUG=True)
                return revised_summary
        except Exception as e:
            logging.info(e)
            return "I don't know"

def processTopicSummary(llm, client, fileName, indexNs, indexType, prospectusSummaryIndexName, embeddings, embeddingModelType, selectedTopics, 
                        summaryPromptTemplate, topK, existingSummary, fullDocumentSummary):
    # r = findFileInIndex(SearchService, SearchKey, prospectusIndexName, fileName)
    # if r.get_count() == 0:
    #     rawDocs = blobLoad(OpenAiDocConnStr, OpenAiDocContainer, fileName)
    #     textSplitter = RecursiveCharacterTextSplitter(chunk_size=int(8000), chunk_overlap=int(1000))
    #     docs = textSplitter.split_documents(rawDocs)
    #     logging.info("Docs " + str(len(docs)))
    #     createSearchIndex(SearchService, SearchKey, prospectusIndexName)
    #     indexSections(OpenAiService, OpenAiKey, OpenAiVersion, OpenAiApiKey, SearchService, SearchKey, embeddingModelType,
    #                    OpenAiEmbedding, fileName, prospectusIndexName, docs)
    # else:
    #     logging.info('Found existing data')
    if fullDocumentSummary:
        selectedTopics.append("FullDocument")

    createProspectusSummary(prospectusSummaryIndexName)
    topicSummary = []
    logging.info(f"Existing Summary: {existingSummary}")
    if existingSummary == "true":
        logging.info(f"Found existing summary")
        r = findSummaryInIndex(SearchService, SearchKey, prospectusSummaryIndexName, fileName, 'prospectus')
        for s in r:
            topicSummary.append(
                {
                    'id' : s['id'],
                    'fileName': s['fileName'],
                    'docType': s['docType'],
                    'topic': s['topic'],
                    'summary': s['summary']
                })
    else:
        for topic in selectedTopics:
            r = findTopicSummaryInIndex(SearchService, SearchKey, prospectusSummaryIndexName, fileName, 'prospectus', topic)
            if r.get_count() == 0:
                logging.info(f"Summarize on Topic: {topic}")
                try:
                    answer = summarizeTopic(llm, client, topic, embeddingModelType, indexNs, indexType, topK)
                    if "I don't know" not in answer:
                        topicSummary.append({
                            'id' : str(uuid.uuid4()),
                            'fileName': fileName,
                            'docType': 'prospectus',
                            'topic': topic,
                            'summary': answer
                    })
                except:
                    logging.info(f"Error in summarizing topic: {topic}")                
            else:
                for s in r:
                    topicSummary.append(
                        {
                            'id' : s['id'],
                            'fileName': s['fileName'],
                            'docType': s['docType'],
                            'topic': s['topic'],
                            'summary': s['summary']
                        })
        mergeDocs(SearchService, SearchKey, prospectusSummaryIndexName, topicSummary)
    return topicSummary

def summarizeTopics(indexNs, indexType, existingSummary, fullDocumentSummary, overrides):
    prospectusSummaryIndexName = 'summary'

    embeddingModelType = overrides.get("embeddingModelType") or 'azureopenai'
    selectedTopics = overrides.get("topics") or []
    summaryPromptTemplate = overrides.get("promptTemplate") or ''
    temperature = overrides.get("temperature") or 0.3
    tokenLength = overrides.get("tokenLength") or 3500
    fileName = overrides.get("fileName") or ''
    topK = overrides.get("top") or 3

    logging.info(f"embeddingModelType: {embeddingModelType}")
    logging.info(f"selectedTopics: {selectedTopics}")
    logging.info(f"summaryPromptTemplate: {summaryPromptTemplate}")
    logging.info(f"temperature: {temperature}")
    logging.info(f"tokenLength: {tokenLength}")
    logging.info(f"fileName: {fileName}")
    logging.info(f"topK: {topK}")

    if summaryPromptTemplate == '':
        summaryPromptTemplate = """You are an AI assistant tasked with summarizing documents from large documents that contains information about Initial Public Offerings. 
        IPO document contains sections with information about the company, its business, strategies, risk, management structure, financial, and other information.
        Your summary should accurately capture the key information in the document while avoiding the omission of any domain-specific words. 
        Please generate a concise and comprehensive summary that includes details. 
        Ensure that the summary is easy to understand and provides an accurate representation. 
        Begin the summary with a brief introduction, followed by the main points.
        Generate the summary with minimum of 7 paragraphs and maximum of 10 paragraphs.
        Please remember to use clear language and maintain the integrity of the original information without missing any important details:
        {text}

        """
    
    if (embeddingModelType == 'azureopenai'):
        llm = AzureChatOpenAI(
                        azure_endpoint=OpenAiEndPoint,
                        api_version=OpenAiVersion,
                        azure_deployment=OpenAiChat,
                        temperature=0.3,
                        api_key=OpenAiKey,
                        max_tokens=3500)
        logging.info("LLM Setup done")
        embeddings = AzureOpenAIEmbeddings(azure_endpoint=OpenAiEndPoint, azure_deployment=OpenAiEmbedding, api_key=OpenAiKey, openai_api_type="azure")
        client = AzureOpenAI(
            api_key=OpenAiKey,  
            api_version=OpenAiVersion,
            azure_endpoint=OpenAiEndPoint,
        )
    elif embeddingModelType == "openai":
        openai.api_type = "open_ai"
        openai.api_base = "https://api.openai.com/v1"
        openai.api_version = '2020-11-07' 
        openai.api_key = OpenAiApiKey
        llm = ChatOpenAI(temperature=temperature,
            openai_api_key=OpenAiApiKey,
            model_name="gpt-3.5-turbo",
            max_tokens=tokenLength)
        embeddings = OpenAIEmbeddings(openai_api_key=OpenAiApiKey)
        client = OpenAI(
            api_key=OpenAiApiKey
        )


    summaryTopicData = processTopicSummary(llm, client, fileName, indexNs, indexType, prospectusSummaryIndexName, embeddings, embeddingModelType, 
                            selectedTopics, summaryPromptTemplate, topK, existingSummary, fullDocumentSummary)
    outputFinalAnswer = {"data_points": '', "answer": summaryTopicData, 
                    "thoughts": '',
                        "sources": '', "nextQuestions": '', "error": ""}
    return outputFinalAnswer

def TransformValue(indexNs, indexType, existingSummary, fullDocumentSummary, record):
    logging.info("Calling Transform Value")
    try:
        recordId = record['recordId']
    except AssertionError  as error:
        return None

    # Validate the inputs
    try:
        assert ('data' in record), "'data' field is required."
        data = record['data']
        assert ('text' in data), "'text' field is required in 'data' object."

    except KeyError as error:
        return (
            {
            "recordId": recordId,
            "errors": [ { "message": "KeyError:" + error.args[0] }   ]
            })
    except AssertionError as error:
        return (
            {
            "recordId": recordId,
            "errors": [ { "message": "AssertionError:" + error.args[0] }   ]
            })
    except SystemError as error:
        return (
            {
            "recordId": recordId,
            "errors": [ { "message": "SystemError:" + error.args[0] }   ]
            })

    try:
        # Getting the items from the values/data/text
        value = data['text']
        overrides = data['overrides']
        summaryResponse = summarizeTopics(indexNs, indexType, existingSummary, fullDocumentSummary, overrides)
        return ({
            "recordId": recordId,
            "data": summaryResponse
            })
    
    except:
        return (
            {
            "recordId": recordId,
            "errors": [ { "message": "Could not complete operation for record." }   ]
            })