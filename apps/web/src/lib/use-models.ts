import { useState, useEffect } from 'react';
import axios from 'axios';
import { billingApi, Model } from './api';

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

let modelsCache: Model[] | null = null;
let modelsPromise: Promise<Model[]> | null = null;

export function useModels() {
    const [models, setModels] = useState<Model[]>(modelsCache || []);
    const [isLoading, setIsLoading] = useState(!modelsCache);
    const [error, setError] = useState<Error | null>(null);

    useEffect(() => {
        if (modelsCache) {
            setModels(modelsCache);
            setIsLoading(false);
            return;
        }

        if (!modelsPromise) {
            modelsPromise = billingApi.getModels()
                .then(res => {
                    modelsCache = res.data.models || [];
                    return modelsCache;
                })
                .catch(() => {
                    // Fallback to public models endpoint (no auth required)
                    return axios.get<{ models: Model[] }>(`${API_BASE_URL}/api/public/models`)
                        .then(res => {
                            modelsCache = res.data.models || [];
                            return modelsCache;
                        });
                });
        }

        modelsPromise.then(data => {
            setModels(data);
            setIsLoading(false);
        }).catch(err => {
            setError(err);
            setIsLoading(false);
            modelsPromise = null;
        });
    }, []);

    return { models, isLoading, error };
}
