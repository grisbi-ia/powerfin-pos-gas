import { describe, it, expect } from 'vitest';
import {
	normalizeIdNumber,
	validateCedula,
	validateRuc,
	validateIdentification,
	isValidIdentification,
	needsIdentification
} from './id-validation';

// Real identifications from production (same vectors as the backend suite).
const SRI_ACCEPTED_CEDULAS = [
	'0101644193', '0105182513', '0106177454', '0104079983', '0101877942',
	'0201522679', '0200893006', '0301086005', '0302112859', '0900600206',
	'0901126763', '0901259390'
];

// The 6 customers that lost their invoice on 2026-09-13 (bad check digit).
const SRI_REJECTED_CEDULAS = [
	'0102126197', '0101867561', '0104888555', '1706248010', '0106190486', '1708860005'
];

// Juridical RUCs the SRI confirms and that invoice today, but that FAIL the
// published module-11 check digit → must never be blocked.
const SRI_ACCEPTED_JURIDICA_RUCS = [
	'1793200847001', '0391035013001', '1793199902001', '0195128571001', '0391034503001'
];

describe('normalizeIdNumber', () => {
	it('strips separators, spaces and case', () => {
		expect(normalizeIdNumber(' 010-164.4193 ')).toBe('0101644193');
		expect(normalizeIdNumber(null)).toBe('');
		expect(normalizeIdNumber(undefined)).toBe('');
	});
});

describe('validateCedula', () => {
	it.each(SRI_ACCEPTED_CEDULAS)('accepts SRI-accepted cédula %s', (cedula) => {
		expect(validateCedula(cedula)).toBeNull();
	});

	it.each(SRI_REJECTED_CEDULAS)('rejects cédula Key49 rejected (%s)', (cedula) => {
		expect(validateCedula(cedula)).toContain('dígito verificador');
	});

	it('accepts a digit-dashed cédula', () => {
		expect(validateCedula('010-164 4193')).toBeNull();
	});

	it('rejects empty, non-numeric and wrong length', () => {
		expect(validateCedula('')).toBe('Ingrese el número de cédula.');
		expect(validateCedula('01016441AB')).toContain('solo números');
		expect(validateCedula('010164419')).toContain('10 dígitos');
		expect(validateCedula('01016441931')).toContain('10 dígitos');
	});

	it('rejects an invalid province', () => {
		expect(validateCedula('0001644193')).toContain('provincia');
		expect(validateCedula('9901644193')).toContain('provincia');
	});
});

describe('validateRuc', () => {
	it.each(SRI_ACCEPTED_JURIDICA_RUCS)('does not block real juridical RUC %s', (ruc) => {
		expect(validateRuc(ruc)).toBeNull();
	});

	it('accepts a natural RUC (cédula + 001)', () => {
		expect(validateRuc('0100086875001')).toBeNull();
	});

	it('rejects a natural RUC whose cédula part is invalid', () => {
		expect(validateRuc('1708860005001')).toContain('dígito verificador');
	});

	it('rejects non-numeric, wrong length, bad province, bad third digit, missing 001', () => {
		expect(validateRuc('GADPAUTE')).toContain('solo números');
		expect(validateRuc('179320084700')).toContain('13 dígitos');
		expect(validateRuc('9993200847001')).toContain('provincia');
		expect(validateRuc('1783200847001')).toContain('tercer dígito');
		expect(validateRuc('1793200847002')).toContain('001');
	});

	it('rejects empty', () => {
		expect(validateRuc('')).toBe('Ingrese el número de RUC.');
	});
});

describe('validateIdentification', () => {
	it('dispatches on the type', () => {
		expect(validateIdentification('CED', '0101644193')).toBeNull();
		expect(validateIdentification('CED', '0102126197')).not.toBeNull();
		expect(validateIdentification('RUC', '1793200847001')).toBeNull();
		expect(validateIdentification('ced', '0101644193')).toBeNull();
	});

	it('rejects an unsupported type', () => {
		expect(validateIdentification('PASAPORTE', '123')).toContain('no soportado');
	});
});

describe('isValidIdentification', () => {
	it('is a boolean shortcut', () => {
		expect(isValidIdentification('CED', '0101644193')).toBe(true);
		expect(isValidIdentification('CED', '0102126197')).toBe(false);
	});
});

describe('needsIdentification', () => {
	it('true when the identification is missing or invalid', () => {
		expect(needsIdentification(null)).toBe(true);
		expect(needsIdentification({ id_type: 'CED', id_number: null })).toBe(true);
		expect(needsIdentification({ id_type: 'CED', id_number: '' })).toBe(true);
		expect(needsIdentification({ id_type: 'CED', id_number: '0102126197' })).toBe(true);
	});

	it('false when the identification is valid', () => {
		expect(needsIdentification({ id_type: 'CED', id_number: '0101644193' })).toBe(false);
		expect(needsIdentification({ id_type: 'RUC', id_number: '1793200847001' })).toBe(false);
	});
});
