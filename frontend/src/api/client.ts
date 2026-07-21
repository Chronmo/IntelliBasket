import axios from "axios";

import type {
  ApiResponse,
  AssociationRule,
  BusinessOverview,
  MonthlySale,
  RfmCustomer,
  RfmSegment,
  RuleDrift,
  TopProduct,
} from "./types";

const apiClient = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || "/api/v1",
  timeout: 15_000,
  headers: { Accept: "application/json" },
});

async function getData<T>(path: string, params?: object): Promise<ApiResponse<T>> {
  const response = await apiClient.get<ApiResponse<T>>(path, { params });
  return response.data;
}

export const analyticsApi = {
  getReadiness: () => getData<{ status: string }>("/health/ready"),
  getOverview: () => getData<BusinessOverview>("/overview"),
  getMonthlySales: () => getData<MonthlySale[]>("/sales/monthly"),
  getSegments: (snapshotDate?: string) =>
    getData<RfmSegment[]>("/rfm/segments", { snapshotDate }),
  getCustomers: (params: {
    segmentCode?: string;
    snapshotDate?: string;
    page?: number;
    pageSize?: number;
  }) => getData<RfmCustomer[]>("/rfm/customers", params),
  getRules: (params: {
    segmentCode?: string;
    minLift?: number;
    minConfidence?: number;
    productCode?: string;
    limit?: number;
  }) => getData<AssociationRule[]>("/association-rules", params),
  getRuleDrift: (params?: { driftStatus?: string; limit?: number }) =>
    getData<RuleDrift[]>("/rule-drift", params),
  getTopProducts: (limit = 20) => getData<TopProduct[]>("/products/top", { limit }),
  getRecommendations: async (payload: {
    segmentCode: string;
    productCode: string;
    minLift: number;
    limit: number;
  }): Promise<ApiResponse<AssociationRule[]>> => {
    const response = await apiClient.post<ApiResponse<AssociationRule[]>>(
      "/marketing-recommendations",
      payload,
    );
    return response.data;
  },
};
