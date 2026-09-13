/**
 * Ecuadorian identification validation (cédula / RUC) — offline mirror.
 *
 * MUST stay in sync with `pos_backend/app/services/id_validation.py`, which is
 * the authority (the backend validates again before storing anything).
 * This copy exists only so the dispatcher gets immediate feedback on the
 * keypad, without a round trip.
 *
 * Rules, measured against production data:
 *  - Cédula: SRI module-10 check digit. This is exactly what Key49 enforces
 *    ("Invalid identification for type 05"); 0 false negatives over 3,743
 *    identifications the SRI had already accepted.
 *  - RUC natural (3rd digit 0-5): cédula check digit + "001".
 *  - RUC jurídica (9) / pública (6): structure ONLY. The published module-11
 *    check digit is NOT enforced because the SRI registry contains RUCs that
 *    fail it (e.g. CLICK SOLUCIONES S.A.S. 1793200847001 invoices normally).
 *    Existence is confirmed by the backend against the SRI registry.
 */

export type IdType = 'CED' | 'RUC';

export const CEDULA_LENGTH = 10;
export const RUC_LENGTH = 13;

/** 01-24 provinces + 30 (exterior / issued abroad). */
const VALID_PROVINCES = new Set([
	...Array.from({ length: 24 }, (_, i) => String(i + 1).padStart(2, '0')),
	'30'
]);

const CEDULA_WEIGHTS = [2, 1, 2, 1, 2, 1, 2, 1, 2];
const RUC_NATURAL_THIRD = new Set(['0', '1', '2', '3', '4', '5']);
const RUC_PUBLICA_THIRD = '6';
const RUC_JURIDICA_THIRD = '9';
const RUC_SUFFIX = '001';

/** Strip spaces/dashes/dots and uppercase (both the keypad and the API add them). */
export function normalizeIdNumber(value: string | null | undefined): string {
	if (!value) return '';
	return String(value).trim().toUpperCase().replace(/[\s\-.…]/g, '');
}

function mod10(digits: string): number {
	let total = 0;
	for (let i = 0; i < digits.length; i++) {
		const product = Number(digits[i]) * CEDULA_WEIGHTS[i];
		total += product > 9 ? product - 9 : product;
	}
	return (10 - (total % 10)) % 10;
}

/** Returns a user-facing error, or null when the cédula is valid. */
export function validateCedula(value: string | null | undefined): string | null {
	const id = normalizeIdNumber(value);

	if (!id) return 'Ingrese el número de cédula.';
	if (!/^\d+$/.test(id)) return 'La cédula debe contener solo números.';
	if (id.length !== CEDULA_LENGTH) return `La cédula debe tener ${CEDULA_LENGTH} dígitos.`;
	if (!VALID_PROVINCES.has(id.slice(0, 2)))
		return `La cédula tiene un código de provincia inválido (${id.slice(0, 2)}). Verifique el número con el cliente.`;
	if (mod10(id.slice(0, 9)) !== Number(id[9]))
		return 'La cédula no es válida (dígito verificador incorrecto). Vuelva a pedir el número al cliente.';
	return null;
}

/**
 * Returns a user-facing error, or null when the RUC passes the blocking rules.
 * Does NOT check existence in the SRI registry (backend responsibility).
 */
export function validateRuc(value: string | null | undefined): string | null {
	const id = normalizeIdNumber(value);

	if (!id) return 'Ingrese el número de RUC.';
	if (!/^\d+$/.test(id)) return 'El RUC debe contener solo números (13 dígitos).';
	if (id.length !== RUC_LENGTH) return `El RUC debe tener ${RUC_LENGTH} dígitos.`;
	if (!VALID_PROVINCES.has(id.slice(0, 2)))
		return `El RUC tiene un código de provincia inválido (${id.slice(0, 2)}). Verifique el número con el cliente.`;

	const third = id[2];
	if (third !== RUC_PUBLICA_THIRD && third !== RUC_JURIDICA_THIRD && !RUC_NATURAL_THIRD.has(third))
		return `El RUC tiene un tercer dígito inválido (${third}). Verifique el número con el cliente.`;
	if (!id.endsWith(RUC_SUFFIX)) return 'El RUC debe terminar en 001 (establecimiento matriz).';

	if (RUC_NATURAL_THIRD.has(third)) {
		// Persona natural: the first 10 digits are the holder's cédula.
		return validateCedula(id.slice(0, CEDULA_LENGTH));
	}
	return null;
}

/** Returns a user-facing error, or null when the identification is valid. */
export function validateIdentification(
	idType: string | null | undefined,
	value: string | null | undefined
): string | null {
	const type = (idType ?? '').trim().toUpperCase();
	if (type !== 'CED' && type !== 'RUC')
		return 'Tipo de identificación no soportado. Use CED (cédula) o RUC.';
	return type === 'CED' ? validateCedula(value) : validateRuc(value);
}

export function isValidIdentification(
	idType: string | null | undefined,
	value: string | null | undefined
): boolean {
	return validateIdentification(idType, value) === null;
}

/**
 * True when the given customer has no usable identification and the dispatcher
 * must ask for it again before billing (the state produced by clearing an
 * invalid cédula/RUC).
 */
export function needsIdentification(person: {
	id_type?: string | null;
	id_number?: string | null;
} | null | undefined): boolean {
	if (!person) return true;
	if (!person.id_number) return true;
	return !isValidIdentification(person.id_type, person.id_number);
}
