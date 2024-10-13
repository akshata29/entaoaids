export const enum Approaches {
    RetrieveThenRead = "rtr",
    ReadRetrieveRead = "rrr",
    ReadDecomposeAsk = "rda"
}

export const enum SearchTypes {
    Similarity = "similarity",
    Hybrid = "hybrid",
    HybridReRank = "hybridrerank"
}

export type ChatRespValues = {
    recordId: number,
    data: AskResponse
};

export type ChatResponse = {
    values: ChatRespValues[];
};


export type AskRequestOverrides = {
    semanticRanker?: boolean;
    semanticCaptions?: boolean;
    excludeCategory?: string;
    top?: number;
    temperature?: number;
    promptTemplate?: string;
    promptTemplatePrefix?: string;
    promptTemplateSuffix?: string;
    suggestFollowupQuestions?: boolean;
    chainType?: string;
    tokenLength?: number;
    indexType?: string;
    indexes?: any;
    autoSpeakAnswers?: boolean;
    embeddingModelType?: string;
    firstSession?: boolean;
    session?: string;
    sessionId?: string;
    functionCall?: boolean;
    useInternet?: boolean;
    deploymentType?: string;
    fileName?: string;
    topics?: string[],
    searchType?: SearchTypes;
};

export type AskRequest = {
    question: string;
    approach: Approaches;
    overrides?: AskRequestOverrides;
};

export type AskResponse = {
    answer: string;
    thoughts: string | null;
    data_points: string[];
    error?: string;
    sources?: string;
    nextQuestions?: string;
};

export type SpeechTokenResponse = {
    Token: string;
    Region: string
};

export type UserInfo = {
    access_token: string;
    expires_on: string;
    id_token: string;
    provider_name: string;
    user_claims: any[];
    user_id: string;
};