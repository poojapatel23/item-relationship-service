/********************************************************************************
 * Copyright (c) 2021,2022
 *       2022: Bayerische Motoren Werke Aktiengesellschaft (BMW AG)
 *       2022: ZF Friedrichshafen AG
 *       2022: ISTOS GmbH
 * Copyright (c) 2021,2022 Contributors to the Eclipse Foundation
 *
 * See the NOTICE file(s) distributed with this work for additional
 * information regarding copyright ownership.
 *
 * This program and the accompanying materials are made available under the
 * terms of the Apache License, Version 2.0 which is available at
 * https://www.apache.org/licenses/LICENSE-2.0. *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
 * WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
 * License for the specific language governing permissions and limitations
 * under the License.
 *
 * SPDX-License-Identifier: Apache-2.0
 ********************************************************************************/
package org.eclipse.tractusx.irs.component.enums;

import com.fasterxml.jackson.annotation.JsonValue;
import lombok.AllArgsConstructor;
import lombok.Getter;

/**
 * Process step information
 */
@Getter
@AllArgsConstructor
public enum ProcessStep {
    SUBMODEL_REQUEST("SubmodelRequest"),
    DIGITAL_TWIN_REQUEST("DigitalTwinRequest"),
    SCHEMA_VALIDATION("SchemaValidation"),
    SCHEMA_REQUEST("SchemaRequest"),
    BPDM_REQUEST("BpdmRequest"),
    BPDM_VALIDATION("BpdmValidation");

    @JsonValue
    private final String value;
}
