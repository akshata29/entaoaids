import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import Markdown from '@pity/vite-plugin-react-markdown'
import EnvironmentPlugin from 'vite-plugin-environment'

// https://vitejs.dev/config/
export default defineConfig({
    plugins: [react(), 
        EnvironmentPlugin('all'),
        Markdown({
        wrapperComponentName: 'ReactMarkdown',
       // wrapperComponentPath: './src/pages/help/help',
      })],
    build: {
        outDir: "../backend/static",
        emptyOutDir: true,
        sourcemap: true
    },
    server: {
        port:5175,
        proxy: {
            "/content": "http://127.0.0.1:5005",
            "/uploadFile": "http://127.0.0.1:5005",
            "/uploadBinaryFile": "http://127.0.0.1:5005",
            "/verifyPassword": "http://127.0.0.1:5005",
            "/summarizer": "http://127.0.0.1:5005",
            "/processSummary": "http://127.0.0.1:5005",
            "/deleteIndexSession": "http://127.0.0.1:5005",
            "/getAllIndexSessions": "http://127.0.0.1:5005",
            "/getAllSessions": "http://127.0.0.1:5005",
            "/getDocumentList": "http://127.0.0.1:5005",
            "/getIndexSession": "http://127.0.0.1:5005",
            "/getIndexSessionDetail": "http://127.0.0.1:5005",
            "/indexManagement": "http://127.0.0.1:5005",
            "/kbQuestionManagement": "http://127.0.0.1:5005",
            "/processDoc": "http://127.0.0.1:5005",
            "/refreshIndex": "http://127.0.0.1:5005",
            "/refreshQuestions": "http://127.0.0.1:5005",
            "/refreshIndexQuestions": "http://127.0.0.1:5005",
            "/renameIndexSession": "http://127.0.0.1:5005"
        }
        // proxy: {
        //     "/ask": {
        //          target: 'http://127.0.0.1:5005',
        //          changeOrigin: true,
        //          secure: false,
        //      }
        // }
    }
});
