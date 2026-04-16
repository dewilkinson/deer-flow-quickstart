export const getBackendBaseURL = () => {
    if (typeof window !== 'undefined') {
        const url = new URL(window.location.href);
        if (url.port === '3000' || url.port === '3001') {
            return `http://${url.hostname}:8000`;
        }
        return `http://${url.hostname}:${url.port}`;
    }
    return process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
};

export const getBackendWSURL = () => {
    const base = getBackendBaseURL();
    return base.replace('http', 'ws');
};

export const getLangGraphBaseURL = getBackendBaseURL;

export * from "./types";
