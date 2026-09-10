/**
 * Admin asset-class master (E10-S4 AC4; api-contracts.md §12.6/12.7).
 *
 * A duplicate `code` is rejected by the API with 409
 * DUPLICATE_ASSET_CLASS_CODE; this screen surfaces `ApiError.message` —
 * the server's own response body — inline next to the `code` field, never a
 * generic "something went wrong" message (AC4).
 */
import type { FormEvent } from 'react';
import { useEffect, useState } from 'react';

import type { AssetClassResponse } from '../../api/admin';
import { createAssetClass, getAssetClasses } from '../../api/admin';
import { ApiError } from '../../api/client';
import { ErrorMessage } from '../../components/ErrorMessage';

export function AssetClasses() {
  const [assetClasses, setAssetClasses] = useState<AssetClassResponse[]>([]);
  const [code, setCode] = useState('');
  const [name, setName] = useState('');
  const [codeError, setCodeError] = useState<string | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  useEffect(() => {
    let cancelled = false;
    getAssetClasses()
      .then((result) => {
        if (!cancelled) {
          setAssetClasses(result);
        }
      })
      .catch(() => {
        if (!cancelled) {
          setLoadError('Asset classes could not be loaded. Please try again.');
        }
      });
    return () => {
      cancelled = true;
    };
  }, []);

  async function handleSubmit(event: FormEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault();
    setCodeError(null);
    setIsSubmitting(true);
    try {
      const created = await createAssetClass({ code, name });
      setAssetClasses((current) => [...current, created]);
      setCode('');
      setName('');
    } catch (err) {
      if (err instanceof ApiError && err.status === 409) {
        setCodeError(err.message);
      } else {
        setCodeError('The asset class could not be added. Please try again.');
      }
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <main className="admin-page">
      <h2>Asset-class master</h2>
      {loadError !== null && <ErrorMessage message={loadError} />}

      <section className="panel">
        <h3>Add an asset class</h3>
        <form onSubmit={(event) => void handleSubmit(event)} noValidate>
          <div className="row">
            <div className="field" style={{ maxWidth: 220 }}>
              <label htmlFor="code">code</label>
              <input
                id="code"
                value={code}
                aria-invalid={codeError !== null}
                aria-describedby="err-asset-code"
                onChange={(event) => setCode(event.target.value)}
              />
              {codeError !== null && (
                <p className="err" id="err-asset-code" role="alert">
                  {codeError}
                </p>
              )}
            </div>
            <div className="field" style={{ maxWidth: 300 }}>
              <label htmlFor="name">name</label>
              <input id="name" value={name} onChange={(event) => setName(event.target.value)} />
            </div>
            <div className="field" style={{ maxWidth: 'none', flex: '0 0 auto' }}>
              <button type="submit" disabled={isSubmitting}>
                Add asset class
              </button>
            </div>
          </div>
        </form>
      </section>

      <section className="panel">
        <h3>Asset-class master</h3>
        <table>
          <thead>
            <tr>
              <th scope="col">id</th>
              <th scope="col">code</th>
              <th scope="col">name</th>
            </tr>
          </thead>
          <tbody>
            {assetClasses.map((assetClass) => (
              <tr key={assetClass.id}>
                <td>{assetClass.id}</td>
                <td>
                  <code className="mono">{assetClass.code}</code>
                </td>
                <td>{assetClass.name}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>
    </main>
  );
}
