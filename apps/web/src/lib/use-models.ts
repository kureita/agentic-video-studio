import { useState, useEffect } from 'react';
import { billingApi, Model } from './api';

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
            modelsPromise = billingApi.getModels().then(res => {
                modelsCache = res.data.models || [];
                return modelsCache;
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
