/** State machine for one inspection request. */

import { useCallback, useState } from 'react';

import { STATUS } from '../constants';
import { createInspection } from '../services/api';

const INITIAL_STATE = Object.freeze({ status: STATUS.IDLE, result: null, error: null });

/** Run one photo through the API and expose loading, result and error states. */
export function useInspection() {
  const [state, setState] = useState(INITIAL_STATE);

  const inspect = useCallback(async (file, options) => {
    setState({ status: STATUS.LOADING, result: null, error: null });
    try {
      const result =
        options !== undefined
          ? await createInspection(file, options)
          : await createInspection(file);
      setState({ status: STATUS.SUCCESS, result, error: null });
      return result;
    } catch (error) {
      setState({ status: STATUS.ERROR, result: null, error });
      return null;
    }
  }, []);

  const reset = useCallback(() => setState(INITIAL_STATE), []);

  return { ...state, inspect, reset };
}
