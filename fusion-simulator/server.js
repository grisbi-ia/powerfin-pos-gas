/**
 * Wayne Fusion Simulator — TCP server that mimics a Synergy/Fusion FCC.
 *
 * Protocol: pipe-delimited text, '^' terminator, no encryption (crypt=5).
 * Listens on port 3011 (same as real Synergy).
 *
 * Usage:  node server.js
 *         node server.js --port 3012
 *
 * Supports: ECHO, SUBSCRIBE, REQ_PUMP_STATUS, REQ_PUMP_PRESET,
 *           REQ_PUMP_CLEAR_PRESET, REQ_PUMP_STOP, REQ_PUMP_CLEAR_STOP,
 *           REQ_GET_FUSION_VERSION, REQ_FCRT_GET_GRAL_CONFIG,
 *           REQ_FCRT_PUMPS_CONFIG, REQ_FCRT_GRADES_CONFIG,
 *           REQ_PAYMENT_TRANSACTION_LOCK, REQ_PAYMENT_CLEAR_SALE,
 *           REQ_PAYMENT_TRANSACTION_UNLOCK, REQ_PAYMENT_UNPAY_SALE
 */

const net = require('net');

const PORT = parseInt(process.argv[3] || process.argv[2] || '3011', 10);
const ECHO_INTERVAL_MS = 110000; // Send ECHO before Fusion timeout (120s)

// ── Logging ─────────────────────────────────────────────────
function log(level, clientId, msg) {
    const ts = new Date().toISOString().replace('T', ' ').slice(0, 19);
    console.log(`[${ts}] [${level}] [${clientId || 'SRV'}] ${msg}`);
}

function parseAddr(socket) {
    return socket.remoteAddress + ':' + socket.remotePort;
}

// ── Message builder ─────────────────────────────────────────
/**
 * Build a Fusion protocol message.
 * Format: <5-digit-len>|5|2||<msgType>|<event>|<dest>|<origin>|<params>|^
 * len = length from '2' (version) to '^' inclusive
 */
function buildMsg(msgType, event, dest, origin, paramsMap) {
    const params = paramsMap
        ? Object.entries(paramsMap)
              .filter(([, v]) => v !== undefined && v !== null)
              .map(([k, v]) => `${k}=${v}`)
              .join('|')
        : '';
    const body = `2||${msgType}|${event}|${dest || ''}|${origin || ''}|${params}|^`;
    const len = body.length;
    return `${String(len).padStart(5, '0')}|5|${body}`;
}

function buildEchoResponse(dest) {
    return buildMsg('ECHO', '', dest, '', {});
}

function buildStatusChange(pumpId, status, subStatus, params = {}) {
    const p = { ...params, ST: status, SU: subStatus || '' };
    return buildMsg('POST', `EVT_PUMP_STATUS_CHANGE_ID_${String(pumpId).padStart(3, '0')}`, '', '', p);
}

function buildNewTransaction(pumpId, params) {
    const now = new Date();
    const dateStr = now.getFullYear() +
        String(now.getMonth() + 1).padStart(2, '0') +
        String(now.getDate()).padStart(2, '0');
    const timeStr = String(now.getHours()).padStart(2, '0') +
        String(now.getMinutes()).padStart(2, '0') +
        String(now.getSeconds()).padStart(2, '0');
    const isoDate = now.toISOString().replace('T', ' ').slice(0, 19);
    const p = {
        ...params,
        DA: dateStr,
        TI: timeStr,
        SDA: dateStr,
        STI: isoDate.slice(11, 19).replace(/:/g, ''),
        FCR: 'NormalCompletion',
    };
    return buildMsg('POST', 'EVT_PUMP_NEW_TRANSACTION', '', '', p);
}

function buildDeliveryProgress(pumpId, params) {
    return buildMsg('POST', `EVT_PUMP_DELIVERY_PROGRESS_ID_${String(pumpId).padStart(3, '0')}`, '', '', params);
}

function buildConfigResponse(event, params) {
    return buildMsg('POST', event, '', '', params);
}

function buildRes(event, params) {
    return buildMsg('POST', event, '', '', params);
}

// ── Pump state machine ──────────────────────────────────────
/**
 * Simulates 4 pumps. Each pump has a configurable number of hoses and grades.
 *
 * Pump 1-2: 8 hoses (matching GASOLINERA)
 * Pump 3-4: 4 hoses
 *
 * Grades per pump: SUPER (1), EXTRA (2), DIESEL (3)
 */

const PUMP_CONFIGS = [
    { pumpId: 1, name: 'Surtidor 1', hoseCount: 8, hoses: [
        { id: 1, grade: 1, gradeName: 'SUPER', price: 1.150 },
        { id: 2, grade: 2, gradeName: 'EXTRA', price: 0.950 },
        { id: 3, grade: 3, gradeName: 'DIESEL', price: 0.750 },
        { id: 4, grade: 1, gradeName: 'SUPER', price: 1.150 },
        { id: 5, grade: 1, gradeName: 'SUPER', price: 1.150 },
        { id: 6, grade: 2, gradeName: 'EXTRA', price: 0.950 },
        { id: 7, grade: 3, gradeName: 'DIESEL', price: 0.750 },
        { id: 8, grade: 1, gradeName: 'SUPER', price: 1.150 },
    ]},
    { pumpId: 2, name: 'Surtidor 2', hoseCount: 8, hoses: [
        { id: 1, grade: 1, gradeName: 'SUPER', price: 1.150 },
        { id: 2, grade: 2, gradeName: 'EXTRA', price: 0.950 },
        { id: 3, grade: 3, gradeName: 'DIESEL', price: 0.750 },
        { id: 4, grade: 1, gradeName: 'SUPER', price: 1.150 },
        { id: 5, grade: 1, gradeName: 'SUPER', price: 1.150 },
        { id: 6, grade: 2, gradeName: 'EXTRA', price: 0.950 },
        { id: 7, grade: 3, gradeName: 'DIESEL', price: 0.750 },
        { id: 8, grade: 1, gradeName: 'SUPER', price: 1.150 },
    ]},
    { pumpId: 3, name: 'Surtidor 3', hoseCount: 4, hoses: [
        { id: 1, grade: 1, gradeName: 'SUPER', price: 1.150 },
        { id: 2, grade: 3, gradeName: 'DIESEL', price: 0.750 },
        { id: 3, grade: 2, gradeName: 'EXTRA', price: 0.950 },
        { id: 4, grade: 1, gradeName: 'SUPER', price: 1.150 },
    ]},
    { pumpId: 4, name: 'Surtidor 4', hoseCount: 4, hoses: [
        { id: 1, grade: 1, gradeName: 'SUPER', price: 1.150 },
        { id: 2, grade: 3, gradeName: 'DIESEL', price: 0.750 },
        { id: 3, grade: 2, gradeName: 'EXTRA', price: 0.950 },
        { id: 4, grade: 1, gradeName: 'SUPER', price: 1.150 },
    ]},
];

// Grade definitions
const GRADES = [
    { id: 1, code: 'SUPER', desc: 'Gasolina Super', level1: 1.150 },
    { id: 2, code: 'EXTRA', desc: 'Gasolina Extra', level1: 0.950 },
    { id: 3, code: 'DIESEL', desc: 'Diesel',       level1: 0.750 },
];

// Initialize pump states
function createPumpState(config) {
    return {
        ...config,
        status: 'IDLE',
        subStatus: '',
        activeHose: null,       // Hose number in use
        presetType: null,       // MONEY or VOLUME
        presetValue: 0,         // Amount or volume
        presetPrice: null,      // Custom price if any
        payIn: '',              // PAY_IN from preset
        payType: '',            // Tipo de pago
        activeSaleId: 0,        // Fusion sale ID (incremented)
        fuelingTimer: null,     // setTimeout for fueling cycle
        stopped: false,         // If STOP was requested
        paused: false,          // If pause was requested
        lockId: null,           // Current lock ID
        saleData: null,         // Last completed sale data
        totalVolume: 0,         // Accumulated volume for totalizers
        totalAmount: 0,         // Accumulated amount
    };
}

const pumps = PUMP_CONFIGS.map(createPumpState);
let nextSaleId = 100;

// ── Timing constants (seconds) ──────────────────────────────
const TIMING = {
    AUTHORIZED_TO_STARTING: 4,   // Time user has to lift the nozzle
    STARTING_TO_FUELLING: 2,     // Brief startup
    FUELLING_DURATION: 6,        // Total fueling time
    PROGRESS_INTERVAL: 1500,     // ms between progress updates
};

// ── Broadcast ───────────────────────────────────────────────
const clients = new Map(); // socket -> { addr, subscriptions: Set, echoTimer }

function broadcast(clientId, msg) {
    for (const [sock, client] of clients) {
        // Check subscription
        const eventName = extractEvent(msg);
        if (client.subscriptions.has('ALL') ||
            client.subscriptions.has(eventName) ||
            matchWildcard(client.subscriptions, eventName)) {
            sock.write(msg + '\n');
        }
    }
}

function extractEvent(msg) {
    // Quick extraction: skip to 6th pipe-delimited field
    const parts = msg.split('|');
    return parts[5] || '';
}

function matchWildcard(subscriptions, event) {
    for (const sub of subscriptions) {
        if (sub.endsWith('*')) {
            const prefix = sub.slice(0, -1);
            if (event.startsWith(prefix)) return true;
        }
        if (sub.includes('_000') && event.match(/_0\d\d$/)) {
            // REQ_PUMP_STATUS_ID_000 matches REQ_PUMP_STATUS_ID_001, etc.
            const subBase = sub.replace(/_000$/, '_');
            if (event.startsWith(subBase)) return true;
        }
    }
    return false;
}

function broadcastAll(sourceId, msg) {
    for (const [sock, client] of clients) {
        if (client.id === sourceId) continue;
        sock.write(msg + '\n');
    }
}

function sendDirect(clientId, msg) {
    const sock = [...clients.keys()].find(s => clients.get(s).id === clientId);
    if (sock) sock.write(msg + '\n');
}

// ── Subscription management ─────────────────────────────────
function addSubscription(client, event) {
    if (event === 'ALL') {
        client.subscriptions.add('ALL');
    } else {
        client.subscriptions.add(event);
    }
    log('DEBUG', client.id, `Subscribed: ${event}`);
}

// ── Pump operations ─────────────────────────────────────────
function findPump(pumpId) {
    return pumps.find(p => p.pumpId === pumpId);
}

function findHose(pump, hoseId) {
    return pump.hoses.find(h => h.id === hoseId);
}

function resetPump(pump) {
    if (pump.fuelingTimer) {
        clearTimeout(pump.fuelingTimer);
        pump.fuelingTimer = null;
    }
    pump.status = 'IDLE';
    pump.subStatus = '';
    pump.activeHose = null;
    pump.presetType = null;
    pump.presetValue = 0;
    pump.presetPrice = null;
    pump.payIn = '';
    pump.payType = '';
    pump.stopped = false;
    pump.paused = false;
}

// ── Fueling simulation ──────────────────────────────────────
function startFueling(clientId, pump, hose, presetType, presetValue, presetPrice, payType, payIn) {
    const saleId = nextSaleId++;
    const startTime = Date.now();
    const price = presetPrice || hose.price;

    // Calculate target volume
    let targetVolume;
    if (presetType === 'MONEY') {
        targetVolume = presetValue / price;
    } else {
        targetVolume = presetValue;
    }

    const targetAmount = presetType === 'MONEY' ? presetValue : presetValue * price;

    pump.activeHose = hose.id;
    pump.presetType = presetType;
    pump.presetValue = presetValue;
    pump.presetPrice = presetPrice;
    pump.payType = payType;
    pump.payIn = payIn;
    pump.activeSaleId = saleId;
    pump.saleData = null;

    // Step 1: AUTHORIZED (immediate)
    pump.status = 'AUTHORIZED';
    pump.subStatus = presetType === 'MONEY' ? 'MONEY_PRESET' : 'VOLUME_PRESET';
    const hosesTotal = pump.hoseCount;
    const authMsg = buildStatusChange(pump.pumpId, 'AUTHORIZED', pump.subStatus, {
        HO: String(hose.id),
        GR: String(hose.grade),
        PR: presetValue.toFixed(2),
        PR_HO: String(hose.id),
        PR_GR: String(hose.grade),
        HN: String(hosesTotal),
        PAY_TY: payType || '',
        PAY_IN: payIn || '',
    });
    log('INFO', clientId, `Pump ${pump.pumpId} Hose ${hose.id}: AUTHORIZED (${presetType}=${presetValue})`);
    broadcast(clientId, authMsg + '\n');

    // Step 2: STARTING (AUTHORIZED_TO_STARTING seconds)
    pump.fuelingTimer = setTimeout(() => {
        pump.status = 'STARTING';
        pump.subStatus = '';
        const startMsg = buildStatusChange(pump.pumpId, 'STARTING', '', {
            HO: String(hose.id),
            GR: String(hose.grade),
            PR: presetValue.toFixed(2),
            HN: String(hosesTotal),
        });
        log('INFO', clientId, `Pump ${pump.pumpId}: STARTING`);
        broadcast(clientId, startMsg + '\n');

        // Step 3: FUELLING (STARTING_TO_FUELLING seconds later)
        pump.fuelingTimer = setTimeout(() => {
            if (pump.stopped || pump.paused) {
                handleStop(pump, clientId);
                return;
            }

            pump.status = 'FUELLING';
            pump.subStatus = '';
            const fuelMsg = buildStatusChange(pump.pumpId, 'FUELLING', '', {
                HO: String(hose.id),
                GR: String(hose.grade),
                PR: presetValue.toFixed(2),
                HN: String(hosesTotal),
            });
            log('INFO', clientId, `Pump ${pump.pumpId}: FUELLING`);
            broadcast(clientId, fuelMsg + '\n');

            // Step 4: Progress updates while FUELLING
            const totalDuration = TIMING.FUELLING_DURATION * 1000;
            const startFuelTime = Date.now();
            let progressCount = 0;
            const maxProgress = Math.ceil(totalDuration / TIMING.PROGRESS_INTERVAL);

            const progressInterval = setInterval(() => {
                progressCount++;
                const elapsed = Date.now() - startFuelTime;
                const progress = Math.min(elapsed / totalDuration, 0.95); // Cap at 95%
                const currentVolume = (targetVolume * progress).toFixed(3);
                const currentAmount = (targetAmount * progress).toFixed(2);
                const deliveredAmount = (targetAmount * (1 - progress)).toFixed(2); // "remaining" for AMS

                const progMsg = buildDeliveryProgress(pump.pumpId, {
                    AM: currentAmount,
                    VO: currentVolume,
                    AMS: currentAmount,
                    PU: price.toFixed(3),
                    HO: String(hose.id),
                    TS: String(Math.floor(Date.now() / 1000)),
                });
                broadcast(clientId, progMsg + '\n');

                if (progressCount >= maxProgress - 1) {
                    clearInterval(progressInterval);
                }
            }, TIMING.PROGRESS_INTERVAL);

            // Step 5: Complete → IDLE + NEW_TRANSACTION
            pump.fuelingTimer = setTimeout(() => {
                clearInterval(progressInterval);

                if (pump.stopped) {
                    handleStop(pump, clientId);
                    return;
                }

                // Final progress: 100%
                const finalMsg = buildDeliveryProgress(pump.pumpId, {
                    AM: targetAmount.toFixed(2),
                    VO: targetVolume.toFixed(3),
                    AMS: targetAmount.toFixed(2),
                    PU: price.toFixed(3),
                    HO: String(hose.id),
                    TS: String(Math.floor(Date.now() / 1000)),
                });
                broadcast(clientId, finalMsg + '\n');

                // IDLE
                pump.status = 'IDLE';
                pump.subStatus = '';
                const fvo = (pump.totalVolume + targetVolume).toFixed(3);
                const fm = (pump.totalAmount + targetAmount).toFixed(2);

                const idleMsg = buildStatusChange(pump.pumpId, 'IDLE', '', {
                    HO: String(hose.id),
                    GR: String(hose.grade),
                    PR: '0.00',
                    HN: String(hosesTotal),
                    PR_HO: '',
                    PR_GR: '',
                });
                broadcast(clientId, idleMsg + '\n');

                // NEW_TRANSACTION
                const txMsg = buildNewTransaction(pump.pumpId, {
                    SA: String(saleId),
                    PM: String(pump.pumpId),
                    HO: String(hose.id),
                    GR: String(hose.grade),
                    VO: targetVolume.toFixed(3),
                    AM: targetAmount.toFixed(2),
                    PU: price.toFixed(3),
                    PR: presetValue.toFixed(2),
                    TY: '1',
                    LV: '1',
                    PAY_TY: payType || 'EFECTIVO',
                    PAY_IN: payIn || '',
                    IVO: pump.totalVolume.toFixed(3),
                    FVO: fvo,
                    IM: pump.totalAmount.toFixed(2),
                    FM: fm,
                    LID: '',
                    SID: '1',
                    ATCVO: '0.000',
                    AVGTM: '25.0',
                });
                log('INFO', clientId, `Pump ${pump.pumpId}: SALE_COMPLETED saleId=${saleId} vol=${targetVolume.toFixed(3)} amt=${targetAmount.toFixed(2)}`);
                broadcast(clientId, txMsg + '\n');

                // Store sale data for payment locks
                pump.saleData = {
                    saleId,
                    pumpId: pump.pumpId,
                    hoseId: hose.id,
                    grade: hose.grade,
                    volume: targetVolume,
                    amount: targetAmount,
                    price,
                    payIn,
                    payType: payType || 'EFECTIVO',
                    presetValue,
                };

                pump.totalVolume += targetVolume;
                pump.totalAmount += targetAmount;
                pump.activeHose = null;
                pump.presetType = null;
                pump.presetValue = 0;
                pump.presetPrice = null;
                pump.fuelingTimer = null;

            }, TIMING.FUELLING_DURATION * 1000);

        }, TIMING.STARTING_TO_FUELLING * 1000);

    }, TIMING.AUTHORIZED_TO_STARTING * 1000);
}

function cancelFueling(pump, clientId) {
    if (pump.fuelingTimer) {
        clearTimeout(pump.fuelingTimer);
        pump.fuelingTimer = null;
    }
    const idleMsg = buildStatusChange(pump.pumpId, 'IDLE', '', {
        HO: String(pump.activeHose || ''),
        GR: String(pump.hoses[0]?.grade || 1),
        PR: '0.00',
        HN: String(pump.hoseCount),
    });
    log('INFO', clientId, `Pump ${pump.pumpId}: CANCELLED → IDLE`);
    broadcast(clientId, idleMsg + '\n');
    resetPump(pump);
}

function handleStop(pump, clientId) {
    if (pump.status === 'FUELLING') {
        pump.status = 'PAUSED';
        pump.subStatus = 'STOPPED';
        pump.paused = true;
    } else {
        pump.status = 'IDLE';
        pump.subStatus = '';
    }
    const msg = buildStatusChange(pump.pumpId, pump.status, pump.subStatus, {
        HO: String(pump.activeHose || ''),
        HN: String(pump.hoseCount),
    });
    broadcast(clientId, msg + '\n');
}

// ── Message handler ─────────────────────────────────────────
function handleMessage(clientId, sock, rawMsg) {
    const msg = parseMessage(rawMsg);
    if (!msg) return;

    const { msgType, event } = msg;
    log('DEBUG', clientId, `Received: ${msgType}|${event}`);

    switch (msgType) {
        case 'ECHO':
            handleEcho(clientId, sock, msg);
            break;

        case 'SUBSCRIBE':
            handleSubscribe(clientId, sock, msg);
            break;

        case 'UNSUBSCRIBE':
            handleUnsubscribe(clientId, sock, msg);
            break;

        case 'POST':
            handlePost(clientId, sock, msg);
            break;

        case 'EXIT':
            handleExit(clientId, sock);
            break;

        default:
            log('WARN', clientId, `Unknown msgType: ${msgType}`);
    }
}

function handleEcho(clientId, sock, msg) {
    const dest = clients.get(sock).addr;
    const resp = buildEchoResponse(dest);
    sock.write(resp + '\n');
    log('DEBUG', clientId, 'ECHO → responded');
}

function handleSubscribe(clientId, sock, msg) {
    const sub = msg.event;
    addSubscription(clients.get(sock), sub);

    // Send current status of all pumps for status subscriptions
    if (sub.includes('PUMP_STATUS') || sub === 'ALL') {
        setTimeout(() => {
            for (const pump of pumps) {
                const statusMsg = buildStatusChange(pump.pumpId, pump.status, pump.subStatus, {
                    HO: String(pump.activeHose || ''),
                    GR: pump.activeHose ? String(findHose(pump, pump.activeHose)?.grade || 1) : '',
                    PR: pump.presetValue ? pump.presetValue.toFixed(2) : '0.00',
                    HN: String(pump.hoseCount),
                    PR_HO: pump.activeHose ? String(pump.activeHose) : '',
                    PR_GR: pump.activeHose ? String(findHose(pump, pump.activeHose)?.grade || 1) : '',
                });
                sock.write(statusMsg + '\n');
            }
        }, 200);
    }
}

function handleUnsubscribe(clientId, sock, msg) {
    const client = clients.get(sock);
    client.subscriptions.delete(msg.event);
    if (msg.event === 'ALL') {
        client.subscriptions.clear();
    }
    log('DEBUG', clientId, `Unsubscribed: ${msg.event}`);
}

function handlePost(clientId, sock, msg) {
    const event = msg.event;

    // ── Pump status requests ───────────────────────────────
    if (event.startsWith('REQ_PUMP_STATUS_ID_')) {
        const pumpId = parseInt(event.split('_').pop(), 10);
        if (pumpId === 0) {
            // All pumps
            setTimeout(() => {
                for (const pump of pumps) {
                    const statusMsg = buildStatusChange(pump.pumpId, pump.status, pump.subStatus, {
                        HO: String(pump.activeHose || ''),
                        GR: pump.activeHose ? String(findHose(pump, pump.activeHose)?.grade || 1) : '',
                        PR: pump.presetValue ? pump.presetValue.toFixed(2) : '0.00',
                        HN: String(pump.hoseCount),
                        PR_HO: pump.activeHose ? String(pump.activeHose) : '',
                        PR_GR: pump.activeHose ? String(findHose(pump, pump.activeHose)?.grade || 1) : '',
                    });
                    sock.write(statusMsg + '\n');
                }
            }, 100);
        } else {
            const pump = findPump(pumpId);
            if (pump) {
                setTimeout(() => {
                    const statusMsg = buildStatusChange(pumpId, pump.status, pump.subStatus, {
                        HO: String(pump.activeHose || ''),
                        GR: pump.activeHose ? String(findHose(pump, pump.activeHose)?.grade || 1) : '',
                        PR: pump.presetValue ? pump.presetValue.toFixed(2) : '0.00',
                        HN: String(pump.hoseCount),
                    });
                    sock.write(statusMsg + '\n');
                }, 50);
            }
        }
        return;
    }

    // ── Pump open ──────────────────────────────────────────
    if (event.startsWith('REQ_PUMP_OPEN_ID_')) {
        const pumpId = parseInt(event.split('_').pop(), 10);
        const targets = pumpId === 0 ? pumps : [findPump(pumpId)].filter(Boolean);
        setTimeout(() => {
            for (const pump of targets) {
                pump.status = 'IDLE';
                pump.subStatus = '';
                const openMsg = buildStatusChange(pump.pumpId, 'IDLE', '', {
                    HN: String(pump.hoseCount),
                });
                sock.write(openMsg + '\n');
                broadcast(clientId, openMsg + '\n');
            }
        }, 100);
        return;
    }

    // ── Pump preset (authorize) ────────────────────────────
    if (event.startsWith('REQ_PUMP_PRESET_ID_')) {
        const pumpId = parseInt(event.split('_').pop(), 10);
        const pump = findPump(pumpId);
        if (!pump) return;

        const params = msg.params || {};

        // Parse hose: "1" or "1@1.100"
        const hoseRaw = params.HO || '1';
        const hoseMatch = hoseRaw.match(/^(\d+)(?:@([\d.]+))?$/);
        const hoseId = hoseMatch ? parseInt(hoseMatch[1], 10) : 1;
        const customPrice = hoseMatch && hoseMatch[2] ? parseFloat(hoseMatch[2]) : undefined;

        const presetType = params.TY || 'MONEY'; // MONEY or VOLUME
        const presetValue = params.VA === 'FULL' ? 9999 : (parseFloat(params.VA) || 50);
        const payType = params.PAY_TY || '';
        const payIn = params.PAY_IN || '';
        const lockId = params.LID || '';
        const fts = params.FTS || '';
        const os = params.OS || '';

        const hose = findHose(pump, hoseId);
        if (!hose) {
            log('WARN', clientId, `Hose ${hoseId} not found on pump ${pumpId}`);
            return;
        }

        // Cancel any active sale
        if (pump.status !== 'IDLE' && pump.fuelingTimer) {
            cancelFueling(pump, clientId);
        }

        log('INFO', clientId, `AUTHORIZE pump=${pumpId} hose=${hoseId} type=${presetType} value=${presetValue} payType=${payType}`);

        // Small delay then start
        setTimeout(() => startFueling(clientId, pump, hose, presetType, presetValue, customPrice, payType, payIn), 300);

        return;
    }

    // ── Pump auth (simple, no preset) ──────────────────────
    if (event.startsWith('REQ_PUMP_AUTH_ID_')) {
        const pumpId = parseInt(event.split('_').pop(), 10);
        const pump = findPump(pumpId);
        if (!pump) return;

        const params = msg.params || {};
        const hoseRaw = params.HO || '1';
        // WARNING: hose ID 0 not allowed, default to 1
        const hoseId = parseInt(hoseRaw.match(/^\d+/)?.[0] || '1', 10) || 1;
        const hose = findHose(pump, hoseId);
        if (!hose) return;

        if (pump.status !== 'IDLE' && pump.fuelingTimer) {
            cancelFueling(pump, clientId);
        }

        setTimeout(() => startFueling(clientId, pump, hose, 'MONEY', 80, undefined, '', ''), 300);
        return;
    }

    // ── Pump clear preset ──────────────────────────────────
    if (event.startsWith('REQ_PUMP_CLEAR_PRESET_ID_')) {
        const pumpId = parseInt(event.split('_').pop(), 10);
        const pump = findPump(pumpId);
        if (pump && pump.status === 'IDLE' && (pump.subStatus.includes('PRESET') || pump.subStatus.includes('PREPAY'))) {
            if (pump.fuelingTimer) {
                clearTimeout(pump.fuelingTimer);
                pump.fuelingTimer = null;
            }
            resetPump(pump);
            const msg = buildStatusChange(pumpId, 'IDLE', '', { HN: String(pump.hoseCount) });
            sock.write(msg + '\n');
            broadcast(clientId, msg + '\n');
        }
        return;
    }

    // ── Pump stop ──────────────────────────────────────────
    if (event.startsWith('REQ_PUMP_STOP_ID_')) {
        const pumpId = parseInt(event.split('_').pop(), 10);
        const targets = pumpId === 0 ? pumps : [findPump(pumpId)].filter(Boolean);
        const params = msg.params || {};
        const pa = params.PA || '1'; // 1=don't wait, 0=wait for current tx

        for (const p of targets) {
            if (pa === '0') {
                p.stopped = true;
            } else {
                if (p.status === 'STARTING' || p.status === 'FUELLING') {
                    handleStop(p, clientId);
                }
                p.stopped = true;
            }
        }
        log('INFO', clientId, `STOP pumpId=${pumpId} wait=${pa}`);
        return;
    }

    // ── Pump clear stop ────────────────────────────────────
    if (event.startsWith('REQ_PUMP_CLEAR_STOP_ID_')) {
        const pumpId = parseInt(event.split('_').pop(), 10);
        const targets = pumpId === 0 ? pumps : [findPump(pumpId)].filter(Boolean);
        for (const p of targets) {
            p.stopped = false;
            if (p.paused) {
                p.paused = false;
                p.status = 'IDLE';
                p.subStatus = '';
                const msg = buildStatusChange(p.pumpId, 'IDLE', '', { HN: String(p.hoseCount) });
                sock.write(msg + '\n');
                broadcast(clientId, msg + '\n');
            }
        }
        return;
    }

    // ── Pump pause ─────────────────────────────────────────
    if (event.startsWith('REQ_PUMP_PAUSE_ID_')) {
        const pumpId = parseInt(event.split('_').pop(), 10);
        const pump = findPump(pumpId);
        if (pump && (pump.status === 'STARTING' || pump.status === 'FUELLING')) {
            handleStop(pump, clientId);
        }
        return;
    }

    // ── Pump reauth (resume from pause) ────────────────────
    if (event.startsWith('REQ_PUMP_REAUTH_ID_')) {
        const pumpId = parseInt(event.split('_').pop(), 10);
        const pump = findPump(pumpId);
        if (pump && pump.paused) {
            pump.paused = false;
            pump.status = 'FUELLING';
            const msg = buildStatusChange(pumpId, 'FUELLING', '', {
                HO: String(pump.activeHose || ''),
                HN: String(pump.hoseCount),
            });
            sock.write(msg + '\n');
            broadcast(clientId, msg + '\n');
        }
        return;
    }

    // ── Payment: transaction lock ──────────────────────────
    if (event === 'REQ_PAYMENT_TRANSACTION_LOCK') {
        const params = msg.params || {};
        const saleId = parseInt(params.SA || '0', 10);
        const lockId = params.LID || '';

        // Find pump with this sale
        for (const pump of pumps) {
            if (pump.saleData?.saleId === saleId) {
                pump.lockId = lockId;
                const resp = buildRes('RES_PAYMENT_TRANSACTION_LOCK', {
                    ST: 'OK',
                    SA: String(saleId),
                    LID: lockId,
                });
                sock.write(resp + '\n');
                log('INFO', clientId, `LOCK saleId=${saleId} lockId=${lockId}`);

                // Broadcast lock event
                const lockEvt = buildMsg('POST', 'EVT_PAYMENT_TRANSACTION_LOCK', '', '', {
                    SA: String(saleId),
                    LID: lockId,
                    PM: String(pump.pumpId),
                });
                broadcast(clientId, lockEvt + '\n');
                return;
            }
        }
        log('WARN', clientId, `LOCK: sale ${saleId} not found`);
        return;
    }

    // ── Payment: clear sale ────────────────────────────────
    if (event === 'REQ_PAYMENT_CLEAR_SALE') {
        const params = msg.params || {};
        const saleId = parseInt(params.SA || '0', 10);

        for (const pump of pumps) {
            if (pump.saleData?.saleId === saleId) {
                const resp = buildRes('RES_PAYMENT_CLEAR_SALE', {
                    ST: 'OK',
                    SA: String(saleId),
                });
                sock.write(resp + '\n');

                // Broadcast cleared event
                const clearedEvt = buildMsg('POST', 'EVT_PAYMENT_SALE_CLEARED', '', '', {
                    SA: String(saleId),
                    PM: String(pump.pumpId),
                });
                broadcast(clientId, clearedEvt + '\n');

                log('INFO', clientId, `PAID saleId=${saleId}`);
                return;
            }
        }
        log('WARN', clientId, `CLEAR: sale ${saleId} not found`);
        return;
    }

    // ── Payment: unlock ────────────────────────────────────
    if (event === 'REQ_PAYMENT_TRANSACTION_UNLOCK') {
        const params = msg.params || {};
        const saleId = parseInt(params.SA || '0', 10);

        for (const pump of pumps) {
            if (pump.saleData?.saleId === saleId) {
                pump.lockId = null;
                const resp = buildRes('RES_PAYMENT_TRANSACTION_UNLOCK', {
                    ST: 'OK',
                    SA: String(saleId),
                });
                sock.write(resp + '\n');

                // Broadcast unlock event
                const unlockEvt = buildMsg('POST', 'EVT_PAYMENT_TRANSACTION_LOCK', '', '', {
                    SA: String(saleId),
                    LID: '',
                    PM: String(pump.pumpId),
                });
                broadcast(clientId, unlockEvt + '\n');
                return;
            }
        }
        return;
    }

    // ── Payment: unpay sale ────────────────────────────────
    if (event === 'REQ_PAYMENT_UNPAY_SALE') {
        const params = msg.params || {};
        const saleId = parseInt(params.SA || '0', 10);

        for (const pump of pumps) {
            if (pump.saleData?.saleId === saleId) {
                const resp = buildRes('RES_PAYMENT_UNPAY_SALE', {
                    ST: 'OK',
                    SA: String(saleId),
                });
                sock.write(resp + '\n');
                return;
            }
        }
        return;
    }

    // ── Payment: pump test ─────────────────────────────────
    if (event === 'REQ_PAYMENT_PUMP_TEST') {
        const params = msg.params || {};
        const saleId = parseInt(params.SA || '0', 10);
        const tank = params.TANK || '';
        log('INFO', clientId, `PUMP_TEST saleId=${saleId} tank=${tank}`);
        return;
    }

    // ── Get sale detail ────────────────────────────────────
    if (event === 'REQ_GET_SALE_DETAIL') {
        const params = msg.params || {};
        const saleId = parseInt(params.SID || params.SA || '0', 10);

        for (const pump of pumps) {
            if (pump.saleData?.saleId === saleId && pump.saleData) {
                const sd = pump.saleData;
                const resp = buildConfigResponse('RES_GET_SALE_DETAIL', {
                    SA: String(sd.saleId),
                    PM: String(sd.pumpId),
                    HO: String(sd.hoseId),
                    GR: String(sd.grade),
                    VO: sd.volume.toFixed(3),
                    AM: sd.amount.toFixed(2),
                    PU: sd.price.toFixed(3),
                    PR: sd.presetValue.toFixed(2),
                    PAY_TY: sd.payType,
                    PAY_IN: sd.payIn,
                    TY: '1',
                    LV: '1',
                });
                sock.write(resp + '\n');
                return;
            }
        }
        return;
    }

    // ── Get pump sales ─────────────────────────────────────
    if (event === 'REQ_GET_PUMP_SALES') {
        const params = msg.params || {};
        const pumpId = parseInt(params.PM || '0', 10);
        const quantity = parseInt(params.QT || '5', 10);
        const pump = findPump(pumpId);

        // We just return a placeholder — real recovery logic needs the DB
        if (pump && pump.saleData) {
            const sd = pump.saleData;
            const resp = buildConfigResponse('RES_GET_PUMP_SALES', {
                SA: String(sd.saleId),
                PM: String(sd.pumpId),
                HO: String(sd.hoseId),
                GR: String(sd.grade),
                VO: sd.volume.toFixed(3),
                AM: sd.amount.toFixed(2),
                PU: sd.price.toFixed(3),
                PR: sd.presetValue.toFixed(2),
                PAY_TY: sd.payType,
                PAY_IN: sd.payIn,
                TY: '1',
            });
            sock.write(resp + '\n');
        }
        return;
    }

    // ── Config: get fusion version ─────────────────────────
    if (event === 'REQ_GET_FUSION_VERSION') {
        setTimeout(() => {
            const resp = buildConfigResponse('RES_GET_FUSION_VERSION', {
                OS: 'SIMULATOR',
                MAC: '00:00:00:00:00:01',
                HWV: 'V2',
                BIN: 'Simulator-1.0',
            });
            sock.write(resp + '\n');
        }, 200);
        return;
    }

    // ── Config: general ────────────────────────────────────
    if (event === 'REQ_FCRT_GET_GRAL_CONFIG') {
        setTimeout(() => {
            const resp = buildConfigResponse('RES_FCRT_GET_GRAL_CONFIG', {
                SNR: '4',
                SNA: 'ESTACION SIMULADA',
                CNY: 'EC',
                MUD: 'DOLLARS',
                MUA: 'USD',
                DF: 'dd/MM/yyyy',
                DCV: '3',
                DCP: '3',
                DCM: '2',
                ATO: '0',
            });
            sock.write(resp + '\n');
        }, 200);
        return;
    }

    // ── Config: pumps ──────────────────────────────────────
    if (event === 'REQ_FCRT_PUMPS_CONFIG') {
        setTimeout(() => {
            const parts = [];
            parts.push('PUMPS=4');
            for (const pump of pumps) {
                parts.push(`P${String(pump.pumpId).padStart(3, '0')}HOSES=${pump.hoseCount}`);
                parts.push(`P${String(pump.pumpId).padStart(3, '0')}LOOPID=Serial_COM${pump.pumpId}_loop`);
                for (const hose of pump.hoses) {
                    parts.push(`P${String(pump.pumpId).padStart(3, '0')}H${hose.id}GRADE=${hose.grade}`);
                    parts.push(`P${String(pump.pumpId).padStart(3, '0')}H${hose.id}PRICE=${hose.price.toFixed(5)}`);
                }
            }
            const resp = buildConfigResponse('RES_FCRT_PUMPS_CONFIG', Object.fromEntries(
                parts.map(p => { const [k, v] = p.split('='); return [k, v]; })
            ));
            sock.write(resp + '\n');
        }, 200);
        return;
    }

    // ── Config: grades ─────────────────────────────────────
    if (event === 'REQ_FCRT_GRADES_CONFIG') {
        setTimeout(() => {
            const parts = [];
            parts.push(`GRADES=${GRADES.length}`);
            for (const g of GRADES) {
                parts.push(`G${String(g.id).padStart(3, '0')}DES=${g.desc}`);
                parts.push(`G${String(g.id).padStart(3, '0')}GNR=${g.id}`);
                parts.push(`G${String(g.id).padStart(3, '0')}L01=${g.level1.toFixed(5)}`);
            }
            const resp = buildConfigResponse('RES_FCRT_GRADES_CONFIG', Object.fromEntries(
                parts.map(p => { const [k, v] = p.split('='); return [k, v]; })
            ));
            sock.write(resp + '\n');
        }, 200);
        return;
    }

    // ── Config: tanks ──────────────────────────────────────
    if (event === 'REQ_FCRT_TANK_CONFIG') {
        setTimeout(() => {
            const resp = buildConfigResponse('RES_FCRT_TANK_CONFIG', {
                TQT: '3',
                T1TAG: 'TANQUE SUPER',
                T1CTY: '20000',
                T1PID: '1',
                T1GID: '1',
                T2TAG: 'TANQUE EXTRA',
                T2CTY: '15000',
                T2PID: '1',
                T2GID: '2',
                T3TAG: 'TANQUE DIESEL',
                T3CTY: '12000',
                T3PID: '1',
                T3GID: '3',
            });
            sock.write(resp + '\n');
        }, 200);
        return;
    }

    // ── Shift close ────────────────────────────────────────
    if (event === 'REQ_SHIFT_CLOSE_PERIOD') {
        const params = msg.params || {};
        const pt = params.PT || 'S';
        setTimeout(() => {
            const resp = buildRes('RES_SHIFT_CLOSE_PERIOD', {
                ST: 'OK',
                PID: String(100 + Math.floor(Math.random() * 900)),
                PT: pt,
            });
            sock.write(resp + '\n');
            log('INFO', clientId, `SHIFT_CLOSE: period=${pt}`);
        }, 500);
        return;
    }

    // ── Prices: set new prices ─────────────────────────────
    if (event === 'REQ_PRICES_SET_NEW_PRICE_CHANGE') {
        setTimeout(() => {
            const resp = buildMsg('POST', 'EVT_NEW_PRICE_CHANGE_APPLIED', '', '', { RC: 'OK' });
            sock.write(resp + '\n');
            broadcastAll(clientId, resp + '\n');
            log('INFO', clientId, 'PRICE_CHANGE applied');
        }, 300);
        return;
    }

    // ── Unknown event ──────────────────────────────────────
    log('DEBUG', clientId, `Unknown event: ${event}`);
}

function handleExit(clientId, sock) {
    log('INFO', clientId, 'EXIT requested — closing');
    sock.end();
}

// ── Message parser ─────────────────────────────────────────
function parseMessage(raw) {
    raw = raw.trim();
    if (!raw.endsWith('^')) return null;

    // Remove trailing ^
    const content = raw.slice(0, -1);
    const parts = content.split('|');

    if (parts.length < 5) return null;

    const msg = {
        len: parts[0],
        crypt: parts[1],
        version: parts[2],
        userId: parts[3] || '',
        msgType: parts[4] || '',
        event: parts[5] || '',
        destination: parts[6] || '',
        origin: parts[7] || '',
        params: {},
    };

    // Parse KEY=VALUE pairs from remaining parts
    for (let i = 8; i < parts.length; i++) {
        const eqIdx = parts[i].indexOf('=');
        if (eqIdx > 0) {
            msg.params[parts[i].substring(0, eqIdx)] = parts[i].substring(eqIdx + 1);
        }
    }

    return msg;
}

// ── TCP Server ──────────────────────────────────────────────
const server = net.createServer((socket) => {
    const addr = parseAddr(socket);
    const clientId = `C${clients.size + 1}`;
    let buffer = '';

    clients.set(socket, {
        id: clientId,
        addr,
        subscriptions: new Set(),
        echoTimer: null,
    });

    socket.setEncoding('utf8');
    socket.setNoDelay(true);
    socket.setTimeout(360000); // 6 min timeout

    log('INFO', clientId, `Connected: ${addr}`);

    // Start ECHO keep-alive
    const echoTimer = setInterval(() => {
        if (socket.destroyed) return;
        try {
            socket.write('00012|5|2||ECHO||||^\r\n');
            log('DEBUG', clientId, 'ECHO → sent');
        } catch (e) {
            clearInterval(echoTimer);
        }
    }, ECHO_INTERVAL_MS);

    clients.get(socket).echoTimer = echoTimer;

    socket.on('data', (data) => {
        buffer += data;
        // Process complete messages (delimited by ^)
        let idx;
        while ((idx = buffer.indexOf('^')) >= 0) {
            const msg = buffer.slice(0, idx + 1);
            buffer = buffer.slice(idx + 1);
            if (msg.trim()) {
                handleMessage(clientId, socket, msg);
            }
        }
    });

    socket.on('close', () => {
        const client = clients.get(socket);
        if (client) {
            clearInterval(client.echoTimer);
        }
        clients.delete(socket);
        log('INFO', clientId, `Disconnected: ${addr}`);
    });

    socket.on('error', (err) => {
        log('ERROR', clientId, `Socket error: ${err.message}`);
        const client = clients.get(socket);
        if (client) clearInterval(client.echoTimer);
        clients.delete(socket);
    });

    socket.on('timeout', () => {
        log('WARN', clientId, 'Timeout — closing');
        socket.end();
    });
});

server.on('error', (err) => {
    console.error(`Server error: ${err.message}`);
    process.exit(1);
});

server.listen(PORT, '0.0.0.0', () => {
    console.log(`\n╔══════════════════════════════════════════════════╗`);
    console.log(`║   Wayne Fusion / Synergy SIMULATOR              ║`);
    console.log(`║                                                 ║`);
    console.log(`║   Puerto TCP: ${String(PORT).padStart(5)}                               ║`);
    console.log(`║   Surtidores: ${String(pumps.length).padStart(5)}                               ║`);
    console.log(`║   Firmware:   Simulator-1.0                     ║`);
    console.log(`║                                                 ║`);
    console.log(`║   Conectar:   telnet localhost ${PORT}             ║`);
    console.log(`║   Health:     echo \"00012|5|2||ECHO||||^\" | nc localhost ${PORT}`);
    console.log(`╚══════════════════════════════════════════════════╝\n`);
    console.log('Surtidores configurados:');
    for (const p of pumps) {
        console.log(`  ${p.name} (ID=${p.pumpId}): ${p.hoseCount} pistolas, estados iniciales: IDLE`);
    }
    console.log(`\nTimings: AUTHORIZED→${TIMING.AUTHORIZED_TO_STARTING}s→STARTING→${TIMING.STARTING_TO_FUELLING}s→FUELLING(${TIMING.FUELLING_DURATION}s)\n`);
});

// Graceful shutdown
process.on('SIGINT', () => {
    console.log('\nShutting down simulator...');
    server.close(() => {
        console.log('Server closed.');
        process.exit(0);
    });
});

process.on('SIGTERM', () => {
    server.close(() => process.exit(0));
});
